"""Watchlist API endpoints — import from Letterboxd, list, and upcoming-showing heads-up."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cinescout.api.dependencies import get_current_user
from cinescout.database import get_db
from cinescout.models import Showing, User, WatchlistItem
from cinescout.schemas.letterboxd import LetterboxdWatchlistImportResponse
from cinescout.schemas.watchlist import UpcomingWatchlistShowingResponse, WatchlistItemResponse
from cinescout.services.film_matcher import FilmMatcher
from cinescout.services.letterboxd_client import LetterboxdClient
from cinescout.services.tmdb_client import TMDbClient

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/watchlist/import", response_model=LetterboxdWatchlistImportResponse)
async def import_watchlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LetterboxdWatchlistImportResponse:
    """
    Sync the current user's watchlist from their public Letterboxd watchlist.

    Full-sync semantics (unlike the append-only diary import): films no
    longer on the remote watchlist are removed locally, since a watchlist
    reflects current intent rather than a history log.

    Matching uses FilmMatcher.match_or_create_film (title/year fuzzy match),
    not match_by_tmdb_id — Letterboxd's watchlist page exposes no TMDb id,
    only a display title/year per entry.
    """
    if not user.letterboxd_username:
        raise HTTPException(status_code=400, detail="No Letterboxd account linked")

    client = LetterboxdClient()
    entries = await client.fetch_watchlist(user.letterboxd_username)
    if entries is None:
        raise HTTPException(
            status_code=502, detail="Could not fetch Letterboxd watchlist — profile may be private"
        )

    film_matcher = FilmMatcher(db, TMDbClient())

    matched_film_ids: set[str] = set()
    for entry in entries:
        film = await film_matcher.match_or_create_film(entry.title, entry.year)
        matched_film_ids.add(film.id)

    existing_stmt = select(WatchlistItem).where(WatchlistItem.user_id == user.id)
    existing_result = await db.execute(existing_stmt)
    existing_items = existing_result.scalars().all()
    existing_film_ids = {item.film_id for item in existing_items}

    removed = 0
    for item in existing_items:
        if item.film_id not in matched_film_ids:
            await db.delete(item)
            removed += 1

    imported = 0
    for film_id in matched_film_ids - existing_film_ids:
        db.add(WatchlistItem(user_id=user.id, film_id=film_id))
        imported += 1

    user.letterboxd_last_synced_at = datetime.now(timezone.utc)
    await db.flush()

    return LetterboxdWatchlistImportResponse(
        status="completed",
        entries_found=len(entries),
        entries_imported=imported,
        entries_removed=removed,
    )


@router.get("/watchlist", response_model=list[WatchlistItemResponse])
async def list_watchlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WatchlistItemResponse]:
    """List the current user's watchlist, alphabetically by film title."""
    stmt = (
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .options(selectinload(WatchlistItem.film))
    )
    result = await db.execute(stmt)
    items = sorted(result.scalars().all(), key=lambda item: item.film.title)
    return [WatchlistItemResponse.model_validate(item) for item in items]


@router.get("/watchlist/upcoming", response_model=list[UpcomingWatchlistShowingResponse])
async def list_upcoming_watchlist_showings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UpcomingWatchlistShowingResponse]:
    """The heads-up: upcoming showings of films on the current user's watchlist."""
    stmt = (
        select(Showing)
        .join(WatchlistItem, WatchlistItem.film_id == Showing.film_id)
        .where(
            WatchlistItem.user_id == user.id,
            Showing.start_time >= datetime.now(timezone.utc),
        )
        .options(selectinload(Showing.film), selectinload(Showing.cinema))
        .order_by(Showing.start_time)
    )
    result = await db.execute(stmt)
    showings = result.scalars().all()
    return [UpcomingWatchlistShowingResponse.model_validate(showing) for showing in showings]
