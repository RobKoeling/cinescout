"""Clean up stale placeholder films.

A placeholder film is created when a cinema title can't be matched to TMDb
(e.g. "Film Club: Certain Women" before the event-series prefix stripping was
added).  Later, a real TMDb film ("Certain Women") may be created for the same
underlying film, leaving the placeholder orphaned *or* still attached to
showings.

This script:
  1. Finds every placeholder film (tmdb_id IS NULL).
  2. For each, checks whether a real TMDb film already exists that covers the
     same title — by looking up normalise_title(placeholder.title) in the
     film_aliases table.
  3. If a real film is found:
       a. Re-links all showings from the placeholder to the real film.
       b. Re-points all aliases that point to the placeholder to the real film.
       c. Deletes the now-orphaned placeholder film.
  4. Prints a summary of every merge and every placeholder left intact.

Run with:
    cd backend
    python -m cinescout.scripts.clean_placeholders
"""

import asyncio
import logging

from sqlalchemy import delete, select

from cinescout.database import AsyncSessionLocal
from cinescout.models.film import Film
from cinescout.models.film_alias import FilmAlias
from cinescout.models.showing import Showing
from cinescout.utils.text import normalise_title

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def clean_placeholders(dry_run: bool = False) -> None:
    tag = "[DRY RUN] " if dry_run else ""

    async with AsyncSessionLocal() as session:
        # Fetch all placeholder films (no TMDb ID)
        placeholders_result = await session.execute(
            select(Film).where(Film.tmdb_id.is_(None))
        )
        placeholders: list[Film] = list(placeholders_result.scalars().all())
        logger.info(f"Found {len(placeholders)} placeholder film(s)")

        merged = 0
        kept = 0

        for placeholder in placeholders:
            normalized = normalise_title(placeholder.title)

            # Look for an alias pointing to a DIFFERENT, real (TMDb) film
            alias_result = await session.execute(
                select(FilmAlias)
                .join(Film, FilmAlias.film_id == Film.id)
                .where(
                    FilmAlias.normalized_title == normalized,
                    FilmAlias.film_id != placeholder.id,
                    Film.tmdb_id.is_not(None),
                )
            )
            alias = alias_result.scalar_one_or_none()

            if alias is None:
                logger.info(f"  KEEP  {placeholder.id!r}  (no TMDb match found for {normalized!r})")
                kept += 1
                continue

            real_film_id = alias.film_id
            logger.info(
                f"  {tag}MERGE  {placeholder.id!r} → {real_film_id!r}"
                f"  (via alias {normalized!r})"
            )

            if not dry_run:
                # Re-link showings one by one, deleting any that would conflict
                # with a showing already linked to the real film at the same time.
                placeholder_showings_result = await session.execute(
                    select(Showing).where(Showing.film_id == placeholder.id)
                )
                placeholder_showings = list(placeholder_showings_result.scalars().all())

                for ps in placeholder_showings:
                    conflict_result = await session.execute(
                        select(Showing).where(
                            Showing.cinema_id == ps.cinema_id,
                            Showing.film_id == real_film_id,
                            Showing.start_time == ps.start_time,
                        )
                    )
                    if conflict_result.scalar_one_or_none():
                        # Real film already has this showing — drop the duplicate
                        await session.delete(ps)
                    else:
                        ps.film_id = real_film_id

                # Re-point aliases that still reference the placeholder,
                # but only when the real film doesn't already have an alias
                # with that normalized_title (would violate the unique constraint).
                stale_aliases_result = await session.execute(
                    select(FilmAlias).where(FilmAlias.film_id == placeholder.id)
                )
                stale_aliases: list[FilmAlias] = list(stale_aliases_result.scalars().all())

                for stale in stale_aliases:
                    # Check whether the real film already owns this normalized_title
                    conflict_result = await session.execute(
                        select(FilmAlias).where(
                            FilmAlias.normalized_title == stale.normalized_title,
                            FilmAlias.film_id == real_film_id,
                        )
                    )
                    if conflict_result.scalar_one_or_none():
                        # Already covered — just delete the duplicate
                        await session.delete(stale)
                    else:
                        stale.film_id = real_film_id

                # Delete the placeholder film (showings + aliases are now re-pointed)
                await session.execute(
                    delete(Film).where(Film.id == placeholder.id)
                )

            merged += 1

        if not dry_run:
            await session.commit()

    logger.info(
        f"\nDone. Merged: {merged}  |  Kept as-is: {kept}"
        + ("  (dry run — no changes written)" if dry_run else "")
    )


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    asyncio.run(clean_placeholders(dry_run=dry_run))
