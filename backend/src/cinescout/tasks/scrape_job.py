"""Scheduled scrape job that fetches showings for all cinemas."""

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cinescout.database import AsyncSessionLocal
from cinescout.models import Cinema, Showing
from cinescout.scrapers import get_scraper
from cinescout.services.film_matcher import FilmMatcher
from cinescout.services.tmdb_client import TMDbClient

logger = logging.getLogger(__name__)

SCRAPE_DAYS_AHEAD = 14


async def run_scrape_all() -> None:
    """Scrape showings for all cinemas and upsert into the database.

    Creates its own DB session so it can be called from the scheduler
    or at startup without depending on a request context.
    """
    logger.info("Starting scheduled scrape for all cinemas")

    date_from = date.today()
    date_to = date_from + timedelta(days=SCRAPE_DAYS_AHEAD)

    async with AsyncSessionLocal() as db:
        # Fetch all cinemas and extract attributes eagerly to avoid
        # lazy-load issues after commits expire ORM objects
        result = await db.execute(select(Cinema))
        cinema_rows = [
            {
                "id": c.id,
                "name": c.name,
                "scraper_type": c.scraper_type,
                "scraper_config": c.scraper_config,
            }
            for c in result.scalars().all()
        ]

        if not cinema_rows:
            logger.warning("No cinemas found in database, skipping scrape")
            return

        logger.info(f"Scraping {len(cinema_rows)} cinemas for {date_from} to {date_to}")

        tmdb_client = TMDbClient()
        film_matcher = FilmMatcher(db, tmdb_client)

        total_showings = 0
        successes = 0
        failures = 0

        for cinema in cinema_rows:
            cinema_id = cinema["id"]
            cinema_name = cinema["name"]
            scraper_type = cinema["scraper_type"]

            scraper = get_scraper(scraper_type, cinema["scraper_config"])
            if not scraper:
                logger.warning(f"No scraper found for {cinema_name} (type: {scraper_type})")
                failures += 1
                continue

            try:
                raw_showings = await scraper.get_showings(date_from, date_to)
                logger.info(f"Found {len(raw_showings)} raw showings for {cinema_name}")

                # Commit any pending film/alias creations before processing showings
                try:
                    await db.commit()
                except IntegrityError:
                    await db.rollback()

                showings_created = 0
                for raw_showing in raw_showings:
                    try:
                        film = await film_matcher.match_or_create_film(raw_showing.title)

                        existing_stmt = select(Showing).where(
                            Showing.cinema_id == cinema_id,
                            Showing.film_id == film.id,
                            Showing.start_time == raw_showing.start_time,
                        )
                        existing_result = await db.execute(existing_stmt)
                        existing_showing = existing_result.scalar_one_or_none()

                        if existing_showing:
                            existing_showing.booking_url = raw_showing.booking_url
                            existing_showing.screen_name = raw_showing.screen_name
                            existing_showing.format_tags = raw_showing.format_tags
                            existing_showing.price = raw_showing.price
                            existing_showing.raw_title = raw_showing.title
                        else:
                            showing = Showing(
                                cinema_id=cinema_id,
                                film_id=film.id,
                                start_time=raw_showing.start_time,
                                booking_url=raw_showing.booking_url,
                                screen_name=raw_showing.screen_name,
                                format_tags=raw_showing.format_tags,
                                price=raw_showing.price,
                                raw_title=raw_showing.title,
                            )
                            db.add(showing)
                            showings_created += 1

                    except Exception as e:
                        logger.error(
                            f"Error processing showing '{raw_showing.title}' "
                            f"at {cinema_name}: {e}",
                            exc_info=True,
                        )

                try:
                    await db.commit()
                except IntegrityError as e:
                    logger.warning(
                        f"Integrity error committing showings for {cinema_name}: {e}"
                    )
                    await db.rollback()

                total_showings += showings_created
                successes += 1
                logger.info(f"Scraped {cinema_name}: {showings_created} new showings")

            except Exception as e:
                logger.error(f"Error scraping {cinema_name}: {e}", exc_info=True)
                failures += 1
                try:
                    await db.rollback()
                except Exception:
                    pass

    logger.info(
        f"Scheduled scrape complete: {successes} succeeded, {failures} failed, "
        f"{total_showings} new showings created"
    )
