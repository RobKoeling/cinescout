"""Merge film records whose stored title contains event-branding or Q&A suffixes.

Before the Ollama-based title extractor was added, the film matcher could create
film records like "Mandy + intro by Josephine Botting, Curator, BFI National Archive"
instead of the canonical "Mandy".  When a later scrape (with Ollama) creates the
correct "Mandy" record, the old record is left behind — and both appear in the
listing for any date that has showings attached to either record.

This script:
  1. Loads every film from the database.
  2. Passes each title through the same two-pass normalisation used by FilmMatcher
     (normalise_title → Ollama extract_film_title).
  3. When the extracted title differs from the stored one it looks for an existing
     canonical film to merge into.
  4a. MERGE — canonical film already exists:
        • All showings pointing to the old film are re-linked to the canonical film
          (duplicates at the same cinema+time are dropped).
        • All aliases pointing to the old film are re-linked (duplicates dropped).
        • The old film record is deleted.
  4b. RENAME — no canonical film exists yet:
        • If the slug-based film ID would stay the same, only the title column is updated.
        • If the ID must change (slug changes), a new film record is created, all
          showings/aliases are migrated, and the old record is deleted.

Run with:
    cd backend
    python -m cinescout.scripts.merge_unstripped_films [--dry-run]
"""

import asyncio
import logging
import re
import sys
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.database import AsyncSessionLocal
from cinescout.models.film import Film
from cinescout.models.film_alias import FilmAlias
from cinescout.models.showing import Showing
from cinescout.services.title_extractor import extract_film_title
from cinescout.utils.text import normalise_title, slugify

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Only process films whose title looks like it might need stripping.
# This pre-filter avoids calling Ollama on clearly clean titles.
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


def _generate_film_id(title: str, year: Optional[int]) -> str:
    slug = slugify(title)
    return f"{slug}-{year}" if year else slug


async def _relink_showings(db: AsyncSession, old_id: str, new_id: str, dry_run: bool) -> int:
    """Re-link showings from old_id to new_id; drop conflicts. Returns count moved."""
    result = await db.execute(select(Showing).where(Showing.film_id == old_id))
    showings = list(result.scalars().all())
    moved = 0
    for s in showings:
        conflict = await db.execute(
            select(Showing).where(
                Showing.cinema_id == s.cinema_id,
                Showing.film_id == new_id,
                Showing.start_time == s.start_time,
            )
        )
        if conflict.scalar_one_or_none():
            if not dry_run:
                await db.delete(s)
        else:
            if not dry_run:
                s.film_id = new_id
            moved += 1
    return moved


async def _relink_aliases(db: AsyncSession, old_id: str, new_id: str, dry_run: bool) -> int:
    """Re-link aliases from old_id to new_id; drop conflicts. Returns count moved."""
    result = await db.execute(select(FilmAlias).where(FilmAlias.film_id == old_id))
    aliases = list(result.scalars().all())
    moved = 0
    for a in aliases:
        conflict = await db.execute(
            select(FilmAlias).where(
                FilmAlias.normalized_title == a.normalized_title,
                FilmAlias.film_id == new_id,
            )
        )
        if conflict.scalar_one_or_none():
            if not dry_run:
                await db.delete(a)
        else:
            if not dry_run:
                a.film_id = new_id
            moved += 1
    return moved


async def merge_unstripped_films(dry_run: bool = False) -> None:
    tag = "[DRY RUN] " if dry_run else ""

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Film))
        all_films: list[Film] = list(result.scalars().all())

    # Filter to plausibly suspicious titles first (cheap regex)
    candidates = [f for f in all_films if _SUSPICIOUS.search(f.title)]
    logger.info(
        f"Checking {len(candidates)} / {len(all_films)} film records through Ollama …"
    )

    merged = skipped = 0

    async with AsyncSessionLocal() as db:
        for film in candidates:
            # Two-pass normalisation (same as FilmMatcher)
            canonical_title = normalise_title(film.title)
            canonical_title = await extract_film_title(canonical_title)

            if canonical_title == film.title:
                skipped += 1
                continue  # Ollama agrees the title is fine

            canonical_id = _generate_film_id(canonical_title, film.year)
            logger.info(
                f"{tag}  {film.id!r} → canonical={canonical_id!r} "
                f"({film.title!r} → {canonical_title!r})"
            )

            # ----------------------------------------------------------------
            # Look for an existing canonical film record
            # ----------------------------------------------------------------
            canonical_film: Film | None = await db.get(Film, canonical_id)

            if canonical_film is None:
                # Try a softer fuzzy lookup (title + year) across all films
                best_score = 0.0
                for f2 in all_films:
                    if f2.id == film.id:
                        continue
                    if film.year is not None and f2.year is not None and abs(film.year - f2.year) > 1:
                        continue
                    score = fuzz.ratio(canonical_title.lower(), f2.title.lower())
                    if score > best_score:
                        best_score = score
                        if score >= 90:
                            canonical_film = f2  # type: ignore[assignment]

            # ----------------------------------------------------------------
            # 4a. Merge into existing canonical film
            # ----------------------------------------------------------------
            if canonical_film and canonical_film.id != film.id:
                n_s = await _relink_showings(db, film.id, canonical_film.id, dry_run)
                n_a = await _relink_aliases(db, film.id, canonical_film.id, dry_run)
                logger.info(
                    f"{tag}  MERGE {film.id!r} → {canonical_film.id!r} "
                    f"({n_s} showings, {n_a} aliases moved)"
                )
                if not dry_run:
                    # Flush alias/showing UPDATEs before the Film DELETE so that
                    # a DB-level CASCADE doesn't delete rows we've already re-linked.
                    await db.flush()
                    await db.execute(delete(Film).where(Film.id == film.id))
                merged += 1

            # ----------------------------------------------------------------
            # 4b. No canonical film exists — skip.
            # Renaming a film in isolation risks corrupting legitimate titles
            # (e.g. Ollama may strip "Looney Tunes:" from a real franchise title,
            # or misidentify the organiser name as the film).  The eval dataset
            # (tests/data/title_extraction_eval.json) is the right place to
            # review and correct these individually.
            # ----------------------------------------------------------------
            else:
                logger.debug(
                    f"  SKIP (no canonical film found) {film.id!r} "
                    f"({film.title!r} → {canonical_title!r})"
                )
                skipped += 1

            # Commit per-film so progress is saved even if we crash partway through
            if not dry_run:
                await db.commit()

    logger.info(
        f"\nDone.  Merged: {merged}  |  Skipped: {skipped}"
        + ("  (dry run — no changes written)" if dry_run else "")
    )


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(merge_unstripped_films(dry_run=dry_run))
