"""
Build (or update) the title-extraction evaluation dataset.

Usage:
    cd backend
    python -m cinescout.scripts.build_title_eval
    python -m cinescout.scripts.build_title_eval --corrections /path/to/title_extraction_eval_corrected.json

What it does
------------
1. Queries showings.raw_title for titles that look like they need stripping
   (colon prefixes, "+ intro/Q&A" suffixes, season/encore qualifiers, etc.)
2. Applies the same two-pass normalisation that FilmMatcher uses
   (normalise_title → extract_film_title via Ollama).
3. Merges results into tests/data/title_extraction_eval.json:
   - Existing entries with a hand-corrected "expected" are preserved as-is.
   - New titles are appended with the model output as the initial "expected".
   - Titles no longer present in the database are kept (they are historical fixtures).

Output format (one object per line would also work; we use a pretty-printed
array for easy manual editing):

    [
      {"raw": "Exhibition on Screen: Frida Kahlo 2026 Encore", "expected": "Frida Kahlo"},
      ...
    ]
"""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make sure the src tree is importable when run as a script
# ---------------------------------------------------------------------------
_REPO_BACKEND = Path(__file__).resolve().parents[3]  # …/backend
sys.path.insert(0, str(_REPO_BACKEND / "src"))

from sqlalchemy import text  # noqa: E402  (after sys.path tweak)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from cinescout.config import settings  # noqa: E402
from cinescout.services.title_extractor import extract_film_title  # noqa: E402
from cinescout.utils.text import normalise_title  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path to the eval fixture file (relative to this script)
# ---------------------------------------------------------------------------
_EVAL_PATH = Path(__file__).resolve().parents[3] / "tests" / "data" / "title_extraction_eval.json"

# ---------------------------------------------------------------------------
# Regex patterns that flag a raw title as "probably needs stripping"
# ---------------------------------------------------------------------------
_SUSPICIOUS = re.compile(
    r"""
    (?:
        .+?:\s          # "Prefix: Title"
        | \+\s          # "+ intro / + Q&A"
        | -\s.*(?:season|birthday|anniversary|tour|special)  # "- Birthday Season"
        | \s\d{4}\s+encore  # "Film 2026 Encore"
        | (?:presents?|season|encore|anniversary)\b  # loose keywords
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


async def _get_suspicious_titles() -> list[str]:
    """Query DB and return distinct suspicious raw_title values, sorted."""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(
            text("SELECT DISTINCT raw_title FROM showings WHERE raw_title IS NOT NULL ORDER BY raw_title")
        )
        all_titles: list[str] = [row[0] for row in result.fetchall()]

    await engine.dispose()

    suspicious = [t for t in all_titles if _SUSPICIOUS.search(t)]
    logger.info(f"Found {len(all_titles)} distinct raw titles; {len(suspicious)} look suspicious")
    return suspicious


async def _build_eval(corrections_path: Path | None = None) -> None:
    # Load existing fixture (preserving any hand-corrected entries).
    # If a corrections file is provided, entries with a "corrected" field
    # replace the model output so the eval reflects ground truth.
    existing: dict[str, str] = {}
    if corrections_path and corrections_path.exists():
        data = json.loads(corrections_path.read_text())
        applied = 0
        for entry in data:
            value = entry.get("corrected", entry["expected"])
            existing[entry["raw"]] = value
            if "corrected" in entry:
                applied += 1
        logger.info(
            f"Loaded {len(existing)} entries from corrections file "
            f"({applied} human corrections applied)"
        )
    elif _EVAL_PATH.exists():
        data = json.loads(_EVAL_PATH.read_text())
        for entry in data:
            existing[entry["raw"]] = entry["expected"]
        logger.info(f"Loaded {len(existing)} existing entries from {_EVAL_PATH}")

    suspicious = await _get_suspicious_titles()

    new_count = 0
    for raw in suspicious:
        if raw in existing:
            continue  # already have an entry (possibly hand-corrected) — skip

        # Two-pass normalisation: regex first, then Ollama
        after_regex = normalise_title(raw)
        extracted = await extract_film_title(after_regex)

        existing[raw] = extracted
        new_count += 1
        if extracted != raw:
            logger.info(f"  {raw!r} → {extracted!r}")
        else:
            logger.debug(f"  {raw!r} (unchanged)")

    logger.info(f"Added {new_count} new entries; total {len(existing)}")

    # Write out sorted by raw title for stable diffs
    entries = [{"raw": k, "expected": v} for k, v in sorted(existing.items())]
    _EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    _EVAL_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {_EVAL_PATH}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--corrections",
        type=Path,
        default=None,
        metavar="FILE",
        help="JSON file with human corrections (entries with a 'corrected' field). "
             "Corrections replace the model-generated 'expected' value.",
    )
    args = parser.parse_args()
    asyncio.run(_build_eval(corrections_path=args.corrections))
