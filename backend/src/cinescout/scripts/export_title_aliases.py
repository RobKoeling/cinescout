"""Export verified title aliases from the local DB for import into production.

Production has no LLM (Ollama only runs locally), so event-style listing titles
("25th Anniversary: Amelie") reach its matcher with only regex cleanup. The
alias table is checked before any fuzzy matching, so shipping known-good
aliases fixes those titles without needing the LLM there.

An alias maps `normalise_title(raw_title)` — exactly the key production computes
— to a film, identified by tmdb_id (film ids can differ between databases).

Candidates come from local showings (raw_title -> film_id) and must pass:
  1. unambiguous: the cleaned key maps to exactly one film locally;
  2. the film has a tmdb_id (no placeholders);
  3. useful: the key differs from the film's own title;
  4. verified: the LLM-extracted title matches the film's title (ratio >= 90),
     which filters out bad local matches.

Usage:
    cd backend
    python -m cinescout.scripts.export_title_aliases --out aliases.json
"""

import argparse
import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz
from sqlalchemy import text

from cinescout.database import AsyncSessionLocal
from cinescout.services.title_extractor import extract_film_title
from cinescout.utils.text import normalise_title

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

VERIFY_THRESHOLD = 90


def _norm(s: str) -> str:
    return " ".join(normalise_title(s).lower().replace(":", " ").split())


async def _build() -> tuple[list[dict], list[dict]]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT s.raw_title, s.film_id, f.title, f.year, f.tmdb_id "
                    "FROM showings s JOIN films f ON f.id = s.film_id "
                    "WHERE s.raw_title IS NOT NULL "
                    "GROUP BY 1, 2, 3, 4, 5"
                )
            )
        ).fetchall()

    by_key: dict[str, dict[str, object]] = defaultdict(dict)
    for r in rows:
        by_key[normalise_title(r.raw_title)][r.film_id] = r

    kept: list[dict] = []
    rejected: list[dict] = []
    keys = sorted(by_key)
    for i, key in enumerate(keys, 1):
        films = by_key[key]
        if len(films) != 1:
            continue
        r = next(iter(films.values()))
        if not r.tmdb_id or _norm(r.title) == _norm(key):
            continue
        extracted = await extract_film_title(key)
        score = fuzz.ratio(_norm(extracted), _norm(r.title))
        entry = {
            "alias": key,
            "tmdb_id": r.tmdb_id,
            "film_id": r.film_id,
            "title": r.title,
            "year": r.year,
            "llm_title": extracted,
            "score": round(score),
        }
        (kept if score >= VERIFY_THRESHOLD else rejected).append(entry)
        if i % 500 == 0:
            print(f"  processed {i}/{len(keys)} keys")
    return kept, rejected


async def main(out: Path) -> None:
    kept, rejected = await _build()
    out.write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n")
    rej = out.with_suffix(".rejected.json")
    rej.write_text(json.dumps(rejected, indent=1, ensure_ascii=False) + "\n")
    print(f"kept {len(kept)} aliases -> {out}")
    print(f"rejected {len(rejected)} -> {rej}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.out))
