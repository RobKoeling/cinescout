"""Letterboxd account linking and diary import endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.api.dependencies import get_current_user
from cinescout.database import get_db
from cinescout.models import User, WatchLog
from cinescout.schemas.letterboxd import LetterboxdImportResponse, LetterboxdLinkRequest
from cinescout.schemas.user import UserResponse
from cinescout.services.film_matcher import FilmMatcher
from cinescout.services.letterboxd_client import LetterboxdClient
from cinescout.services.tmdb_client import TMDbClient

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/letterboxd/link", response_model=UserResponse)
async def link_letterboxd(
    payload: LetterboxdLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Link a Letterboxd username to the current user's account.

    Only hard-rejects on a *confirmed* nonexistent profile (404) — if the
    existence check itself fails (network hiccup), linking still proceeds
    rather than blocking the user on a flaky external request.
    """
    client = LetterboxdClient()
    exists = await client.profile_exists(payload.letterboxd_username)
    if exists is False:
        raise HTTPException(status_code=404, detail="Letterboxd profile not found")

    user.letterboxd_username = payload.letterboxd_username
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/letterboxd/link", response_model=UserResponse)
async def unlink_letterboxd(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Unlink the current user's Letterboxd account."""
    user.letterboxd_username = None
    user.letterboxd_last_synced_at = None
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/letterboxd/import", response_model=LetterboxdImportResponse)
async def import_letterboxd_diary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LetterboxdImportResponse:
    """
    Import the current user's Letterboxd diary via their public RSS feed.

    Synchronous — runs the fetch/match/create inline and returns a summary.
    Matching: prefer the entry's tmdb_id (fetching/creating the Film if it's
    not yet in our DB); entries with no tmdb_id are skipped and counted as
    unmatched rather than risking a low-confidence fuzzy-matched or
    placeholder Film row from a bulk third-party import.
    """
    if not user.letterboxd_username:
        raise HTTPException(status_code=400, detail="No Letterboxd account linked")

    client = LetterboxdClient()
    entries = await client.fetch_diary(user.letterboxd_username)
    if entries is None:
        raise HTTPException(
            status_code=502, detail="Could not fetch Letterboxd diary — profile may be private"
        )

    film_matcher = FilmMatcher(db, TMDbClient())

    imported = 0
    skipped_duplicate = 0
    unmatched = 0

    for entry in entries:
        if entry.tmdb_id is None:
            unmatched += 1
            continue

        film = await film_matcher.match_by_tmdb_id(entry.tmdb_id)
        if film is None:
            unmatched += 1
            continue

        # Soft dedup heuristic (not a DB constraint): skip if this user
        # already has a manual-style entry for this film on this date.
        existing_stmt = select(WatchLog).where(
            WatchLog.user_id == user.id,
            WatchLog.film_id == film.id,
            WatchLog.watched_date == entry.watched_date,
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalar_one_or_none() is not None:
            skipped_duplicate += 1
            continue

        log = WatchLog(
            user_id=user.id,
            film_id=film.id,
            showing_id=None,
            watched_date=entry.watched_date,
            rating=entry.rating,
            comment=None,
        )
        db.add(log)
        await db.flush()
        imported += 1

    user.letterboxd_last_synced_at = datetime.now(timezone.utc)
    await db.flush()

    return LetterboxdImportResponse(
        status="completed",
        entries_found=len(entries),
        entries_imported=imported,
        entries_skipped_duplicate=skipped_duplicate,
        entries_unmatched=unmatched,
    )
