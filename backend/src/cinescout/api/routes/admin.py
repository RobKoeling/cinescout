"""Admin API endpoints for manual operations."""

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.database import get_db
from cinescout.models import Cinema, Film, Showing
from cinescout.scrapers import get_scraper
from cinescout.services.film_matcher import FilmMatcher
from cinescout.services.tmdb_client import TMDbClient
from cinescout.tasks.scrape_job import run_scrape_all

logger = logging.getLogger(__name__)
router = APIRouter()


class ScrapeRequest(BaseModel):
    """Request model for triggering a scrape."""

    cinema_ids: list[str]
    date_from: date
    date_to: date


class CinemaScrapeResult(BaseModel):
    """Result for a single cinema scrape."""

    cinema_id: str
    cinema_name: str
    success: bool
    showings_created: int
    error: str | None = None


class ScrapeResponse(BaseModel):
    """Response for scrape operation."""

    status: str
    results: list[CinemaScrapeResult]
    total_showings: int


@router.post("/admin/scrape", response_model=ScrapeResponse)
async def trigger_scrape(
    request: ScrapeRequest,
    db: AsyncSession = Depends(get_db),
) -> ScrapeResponse:
    """
    Manually trigger a scrape for specific cinemas.

    This endpoint:
    1. Fetches showings from cinema websites
    2. Matches film titles to TMDb data
    3. Stores showings in the database

    Note: This is a synchronous operation that may take several seconds.
    For production, consider using a background task queue.
    """
    # Fetch cinema records
    stmt = select(Cinema).where(Cinema.id.in_(request.cinema_ids))
    result = await db.execute(stmt)
    cinemas = result.scalars().all()

    if not cinemas:
        raise HTTPException(status_code=404, detail="No cinemas found with provided IDs")

    # Initialize services
    tmdb_client = TMDbClient()
    film_matcher = FilmMatcher(db, tmdb_client)

    # Process each cinema
    results: list[CinemaScrapeResult] = []
    total_showings = 0

    for cinema in cinemas:
        # Capture cinema attributes before any potential rollback
        cinema_id = cinema.id
        cinema_name = cinema.name
        scraper_type = cinema.scraper_type

        logger.info(f"Scraping {cinema_name} ({cinema_id})")

        # Get scraper for this cinema
        scraper = get_scraper(scraper_type, cinema.scraper_config)
        if not scraper:
            results.append(
                CinemaScrapeResult(
                    cinema_id=cinema_id,
                    cinema_name=cinema_name,
                    success=False,
                    showings_created=0,
                    error=f"No scraper found for type: {scraper_type}",
                )
            )
            continue

        try:
            # Fetch raw showings
            raw_showings = await scraper.get_showings(request.date_from, request.date_to)
            logger.info(f"Found {len(raw_showings)} raw showings for {cinema_name}")

            # Commit any pending film/alias creations before processing showings
            try:
                await db.commit()
            except IntegrityError:
                # Ignore duplicate key violations (film aliases already exist)
                await db.rollback()

            # Process each showing
            showings_created = 0
            for raw_showing in raw_showings:
                try:
                    # Match or create film
                    film = await film_matcher.match_or_create_film(raw_showing.title)

                    # Check if showing already exists
                    existing_stmt = select(Showing).where(
                        Showing.cinema_id == cinema_id,
                        Showing.film_id == film.id,
                        Showing.start_time == raw_showing.start_time,
                    )
                    existing_result = await db.execute(existing_stmt)
                    existing_showing = existing_result.scalar_one_or_none()

                    if existing_showing:
                        # Update existing showing
                        existing_showing.booking_url = raw_showing.booking_url
                        existing_showing.screen_name = raw_showing.screen_name
                        existing_showing.format_tags = raw_showing.format_tags
                        existing_showing.price = raw_showing.price
                        existing_showing.raw_title = raw_showing.title
                    elif film.tmdb_id is not None:
                        # Check if a placeholder showing exists at the same time/cinema
                        # (happens when a previous scrape stored the film as a placeholder
                        # before TMDb matching worked, e.g. "Film Club: Certain Women").
                        # Migrate it to the real film rather than creating a duplicate.
                        placeholder_stmt = (
                            select(Showing)
                            .join(Film, Showing.film_id == Film.id)
                            .where(
                                Showing.cinema_id == cinema_id,
                                Showing.start_time == raw_showing.start_time,
                                Film.tmdb_id.is_(None),
                            )
                        )
                        placeholder_result = await db.execute(placeholder_stmt)
                        placeholder_showing = placeholder_result.scalar_one_or_none()
                        if placeholder_showing:
                            logger.info(
                                f"Migrating placeholder showing {placeholder_showing.film_id!r}"
                                f" → {film.id!r} for {raw_showing.title!r}"
                            )
                            placeholder_showing.film_id = film.id
                            placeholder_showing.booking_url = raw_showing.booking_url
                            placeholder_showing.screen_name = raw_showing.screen_name
                            placeholder_showing.format_tags = raw_showing.format_tags
                            placeholder_showing.price = raw_showing.price
                            placeholder_showing.raw_title = raw_showing.title
                            existing_showing = placeholder_showing  # suppress the create below

                    if not existing_showing:
                        # Create new showing — flush immediately so the next iteration's
                        # duplicate check can see it, and use a savepoint so an unexpected
                        # IntegrityError only rolls back this one showing.
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
                        try:
                            async with db.begin_nested():
                                db.add(showing)
                                await db.flush()
                            showings_created += 1
                        except IntegrityError:
                            logger.debug(
                                f"Duplicate showing skipped: {raw_showing.title} "
                                f"at {raw_showing.start_time}"
                            )

                except Exception as e:
                    logger.error(
                        f"Error processing showing '{raw_showing.title}' at {cinema_name}: {e}",
                        exc_info=True,
                    )
                    # Continue with next showing

            # Commit all showings for this cinema
            try:
                await db.commit()
            except IntegrityError as e:
                logger.warning(f"Integrity error committing showings for {cinema_name}: {e}")
                await db.rollback()
                # Still count this as success since the error is expected

            results.append(
                CinemaScrapeResult(
                    cinema_id=cinema_id,
                    cinema_name=cinema_name,
                    success=True,
                    showings_created=showings_created,
                )
            )
            total_showings += showings_created

        except Exception as e:
            logger.error(f"Error scraping {cinema_name}: {e}", exc_info=True)
            results.append(
                CinemaScrapeResult(
                    cinema_id=cinema_id,
                    cinema_name=cinema_name,
                    success=False,
                    showings_created=0,
                    error=str(e),
                )
            )

    return ScrapeResponse(
        status="completed",
        results=results,
        total_showings=total_showings,
    )


@router.post("/admin/scrape-all")
async def trigger_scrape_all(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger a full scrape of all cinemas as a background task.

    Returns immediately; the scrape runs asynchronously.
    """
    background_tasks.add_task(run_scrape_all)
    return {"status": "started"}
