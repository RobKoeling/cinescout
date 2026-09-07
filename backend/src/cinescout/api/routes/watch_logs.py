"""Watch-log API endpoints — a user's record of films they've watched."""

import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cinescout.api.dependencies import get_current_user
from cinescout.database import get_db
from cinescout.models import Film, Showing, User, WatchLog
from cinescout.schemas.cinema import CinemaResponse
from cinescout.schemas.film import FilmResponse
from cinescout.schemas.watch_log import WatchLogCreate, WatchLogResponse, WatchLogWithFilmResponse

logger = logging.getLogger(__name__)
router = APIRouter()

LONDON_TZ = ZoneInfo("Europe/London")


def _to_response(watch_log: WatchLog) -> WatchLogWithFilmResponse:
    return WatchLogWithFilmResponse(
        id=watch_log.id,
        film_id=watch_log.film_id,
        showing_id=watch_log.showing_id,
        watched_date=watch_log.watched_date,
        rating=float(watch_log.rating) if watch_log.rating is not None else None,
        comment=watch_log.comment,
        created_at=watch_log.created_at,
        film=FilmResponse.model_validate(watch_log.film),
        cinema=(
            CinemaResponse.model_validate(watch_log.showing.cinema)
            if watch_log.showing is not None
            else None
        ),
    )


@router.post("/watch-logs", response_model=WatchLogResponse, status_code=status.HTTP_201_CREATED)
async def create_watch_log(
    payload: WatchLogCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchLogResponse:
    """Log a film as watched — either a tracked showing or a manual entry."""
    if payload.showing_id is not None:
        showing = await db.get(Showing, payload.showing_id)
        if showing is None:
            raise HTTPException(status_code=404, detail="Showing not found")
        film_id = showing.film_id
        watched_date = showing.start_time.astimezone(LONDON_TZ).date()
    else:
        # Schema validation guarantees film_id/watched_date are set here.
        film = await db.get(Film, payload.film_id)
        if film is None:
            raise HTTPException(status_code=404, detail="Film not found")
        film_id = film.id
        assert payload.watched_date is not None
        watched_date = payload.watched_date

    log = WatchLog(
        user_id=user.id,
        film_id=film_id,
        showing_id=payload.showing_id,
        watched_date=watched_date,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(log)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="This showing is already logged as watched"
        )
    await db.refresh(log)
    return WatchLogResponse.model_validate(log)


@router.get("/watch-logs", response_model=list[WatchLogWithFilmResponse])
async def list_watch_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WatchLogWithFilmResponse]:
    """List the current user's diary, most recently watched first."""
    stmt = (
        select(WatchLog)
        .where(WatchLog.user_id == user.id)
        .options(
            selectinload(WatchLog.film),
            selectinload(WatchLog.showing).selectinload(Showing.cinema),
        )
        .order_by(WatchLog.watched_date.desc(), WatchLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [_to_response(log) for log in logs]


@router.get("/watch-logs/{watch_log_id}", response_model=WatchLogWithFilmResponse)
async def get_watch_log(
    watch_log_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchLogWithFilmResponse:
    """Get a single watch-log entry, if owned by the current user."""
    stmt = (
        select(WatchLog)
        .where(WatchLog.id == watch_log_id, WatchLog.user_id == user.id)
        .options(
            selectinload(WatchLog.film),
            selectinload(WatchLog.showing).selectinload(Showing.cinema),
        )
    )
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Watch log entry not found")
    return _to_response(log)


@router.delete("/watch-logs/{watch_log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watch_log(
    watch_log_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a watch-log entry, if owned by the current user."""
    stmt = select(WatchLog).where(WatchLog.id == watch_log_id, WatchLog.user_id == user.id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Watch log entry not found")
    await db.delete(log)
