"""Backfill TMDb metadata for existing films that have null directors/countries/cast."""

import asyncio
import logging

from sqlalchemy import select

from cinescout.database import AsyncSessionLocal
from cinescout.models.film import Film
from cinescout.services.tmdb_client import TMDbClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _extract_year(release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return int(release_date[:4])
    except (ValueError, IndexError):
        return None


async def backfill() -> None:
    tmdb = TMDbClient()
    if not tmdb.api_key:
        logger.error("TMDB_API_KEY not set — cannot backfill")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Film))
        films: list[Film] = list(result.scalars().all())

    logger.info(f"Found {len(films)} films in database")
    updated = 0
    skipped = 0

    for film in films:
        # Skip if already has metadata
        if film.directors is not None or film.countries is not None or film.year is not None:
            skipped += 1
            continue

        details = None

        # Try to fetch by tmdb_id first (fast, no ambiguity)
        if film.tmdb_id:
            details = await tmdb.get_film_details(film.tmdb_id)

        # Fallback: search by title
        if not details:
            search = await tmdb.search_film(film.title, film.year)
            if search:
                details = await tmdb.get_film_details(search["id"])

        if not details:
            logger.warning(f"No TMDb data found for: {film.title!r}")
            continue

        directors = tmdb.extract_directors(details.get("credits", {}))
        countries = tmdb.extract_countries(details)
        cast = tmdb.extract_cast(details.get("credits", {}))
        year = _extract_year(details.get("release_date"))
        overview = details.get("overview") or None
        poster_path = details.get("poster_path") or None
        runtime = details.get("runtime") or None
        tmdb_id = details.get("id")

        try:
            async with AsyncSessionLocal() as db:
                refreshed = await db.get(Film, film.id)
                if refreshed is None:
                    continue
                refreshed.directors = directors if directors else None
                refreshed.countries = countries if countries else None
                refreshed.cast = cast if cast else None
                refreshed.year = year
                refreshed.overview = overview
                refreshed.poster_path = poster_path
                refreshed.runtime = runtime
                if tmdb_id and not refreshed.tmdb_id:
                    refreshed.tmdb_id = tmdb_id
                await db.commit()
        except Exception as e:
            logger.warning(f"Could not update {film.title!r}: {e}")
            continue

        logger.info(
            f"Updated {film.title!r}: dir={directors}, countries={countries}, "
            f"year={year}, cast={cast}"
        )
        updated += 1

    logger.info(f"Done — updated {updated}, skipped {skipped} (already had metadata)")


if __name__ == "__main__":
    asyncio.run(backfill())
