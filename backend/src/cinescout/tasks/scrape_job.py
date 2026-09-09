"""Scheduled scrape job that fetches showings for all cinemas."""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal, TypedDict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from cinescout.database import AsyncSessionLocal
from cinescout.models import Cinema, Showing
from cinescout.scrapers import get_scraper
from cinescout.services.film_matcher import FilmMatcher
from cinescout.services.tmdb_client import TMDbClient

logger = logging.getLogger(__name__)

SCRAPE_DAYS_AHEAD = 14

# Hard ceiling per cinema so one hung scraper (e.g. a Playwright launch that
# never returns under Fly's memory-constrained containers) can't starve every
# cinema later in the batch.
SCRAPER_TIMEOUT_SECONDS = 120


class CinemaScrapeResult(TypedDict):
    name: str
    count: int
    ok: bool
    error: str | None


class ScrapeProgress(TypedDict):
    status: Literal["idle", "running", "done"]
    total: int
    completed: int
    started_at: datetime | None
    finished_at: datetime | None
    results: list[CinemaScrapeResult]


# Process-local progress state for the currently (or most recently) running
# scrape, polled by the admin Tools page. Fine to keep in-memory: the app
# runs as a single Fly machine and this is monitoring state, not data.
_progress: ScrapeProgress = {
    "status": "idle",
    "total": 0,
    "completed": 0,
    "started_at": None,
    "finished_at": None,
    "results": [],
}


def get_scrape_progress() -> ScrapeProgress:
    return _progress


def mark_scrape_pending() -> None:
    """Flip status to 'running' immediately when a scrape is triggered.

    Called synchronously by the admin view before the actual scrape task
    starts, so the Tools page shows "Running" (and starts auto-refreshing)
    right away instead of the previous run's stale "done" state until the
    background task gets its first chance to run.
    """
    _progress["status"] = "running"
    _progress["completed"] = 0
    _progress["results"] = []
    _progress["started_at"] = datetime.now(timezone.utc)
    _progress["finished_at"] = None


def _reset_progress(total: int) -> None:
    _progress["status"] = "running"
    _progress["total"] = total
    _progress["completed"] = 0
    _progress["started_at"] = datetime.now(timezone.utc)
    _progress["finished_at"] = None
    _progress["results"] = []


def _record_progress(name: str, count: int, ok: bool, error: str | None = None) -> None:
    _progress["results"].append({"name": name, "count": count, "ok": ok, "error": error})
    _progress["completed"] += 1


def _finish_progress() -> None:
    _progress["status"] = "done"
    _progress["finished_at"] = datetime.now(timezone.utc)


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
        _reset_progress(len(cinema_rows))
        try:
            await _scrape_cinemas(db, cinema_rows, date_from, date_to)
        finally:
            _finish_progress()


async def run_scrape_selected(cinema_ids: list[str]) -> None:
    """Scrape showings only for the specified cinema IDs.

    Intended for ad-hoc re-scrapes of individual cinemas from the admin UI.
    """
    logger.info(f"Starting selective scrape for cinema IDs: {cinema_ids}")

    date_from = date.today()
    date_to = date_from + timedelta(days=SCRAPE_DAYS_AHEAD)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Cinema).where(Cinema.id.in_(cinema_ids))
        )
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
            logger.warning("No matching cinemas found for selective scrape")
            return

        logger.info(f"Scraping {len(cinema_rows)} cinemas for {date_from} to {date_to}")
        _reset_progress(len(cinema_rows))
        try:
            await _scrape_cinemas(db, cinema_rows, date_from, date_to)
        finally:
            _finish_progress()


async def _scrape_cinemas(
    db: object,
    cinema_rows: list[dict],
    date_from: date,
    date_to: date,
) -> None:
    """Core scrape loop: fetch and upsert showings for the given cinema rows."""
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
            _record_progress(cinema_name, 0, ok=False, error="no scraper registered")
            continue

        try:
            try:
                raw_showings = await asyncio.wait_for(
                    scraper.get_showings(date_from, date_to),
                    timeout=SCRAPER_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Scraper for {cinema_name} timed out after "
                    f"{SCRAPER_TIMEOUT_SECONDS}s — skipping"
                )
                failures += 1
                _record_progress(
                    cinema_name, 0, ok=False, error=f"timed out after {SCRAPER_TIMEOUT_SECONDS}s"
                )
                continue

            if raw_showings:
                logger.info(f"Found {len(raw_showings)} raw showings for {cinema_name}")
            else:
                logger.warning(f"Scraper returned 0 showings for {cinema_name} — possible scraper issue")

            # Commit any pending film/alias creations before processing showings
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()

            showings_created = 0
            for raw_showing in raw_showings:
                try:
                    film = await film_matcher.match_or_create_film(raw_showing.title, year=raw_showing.year)

                    stmt = (
                        pg_insert(Showing)
                        .values(
                            cinema_id=cinema_id,
                            film_id=film.id,
                            start_time=raw_showing.start_time,
                            booking_url=raw_showing.booking_url,
                            screen_name=raw_showing.screen_name,
                            format_tags=raw_showing.format_tags,
                            price=raw_showing.price,
                            raw_title=raw_showing.title,
                        )
                        .on_conflict_do_update(
                            constraint="uq_cinema_film_time",
                            set_=dict(
                                booking_url=raw_showing.booking_url,
                                screen_name=raw_showing.screen_name,
                                format_tags=raw_showing.format_tags,
                                price=raw_showing.price,
                                raw_title=raw_showing.title,
                                updated_at=func.now(),
                            ),
                        )
                    )
                    result = await db.execute(stmt)
                    if result.rowcount == 1:
                        showings_created += 1

                except Exception as e:
                    logger.error(
                        f"Error processing showing '{raw_showing.title}' "
                        f"at {cinema_name}: {e}",
                        exc_info=True,
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass

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
            _record_progress(cinema_name, showings_created, ok=True)

        except Exception as e:
            logger.error(f"Error scraping {cinema_name}: {e}", exc_info=True)
            failures += 1
            _record_progress(cinema_name, 0, ok=False, error=str(e))
            try:
                await db.rollback()
            except Exception:
                pass

    logger.info(
        f"Scrape complete: {successes} succeeded, {failures} failed, "
        f"{total_showings} new showings created"
    )
