"""Tests for the watch-log API endpoints."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from cinescout.api.dependencies import get_current_user
from cinescout.api.routes import watch_logs
from cinescout.database import get_db
from cinescout.models import Cinema, Film, Showing, User

LONDON_TZ = ZoneInfo("Europe/London")

USER = User(id=1, username="alice", password_hash="x", is_active=True)


def make_film(id: str = "nosferatu-2024") -> Film:
    return Film(
        id=id,
        title="Nosferatu",
        year=2024,
        directors=None,
        countries=None,
        overview=None,
        poster_path=None,
        runtime=132,
        tmdb_id=12345,
    )


def make_cinema(id: str = "bfi-southbank") -> Cinema:
    return Cinema(
        id=id,
        name="BFI Southbank",
        city="london",
        address="Belvedere Road",
        postcode="SE1 8XT",
        scraper_type="bfi",
    )


def make_showing(
    id: int = 1, film_id: str = "nosferatu-2024", cinema_id: str = "bfi-southbank"
) -> Showing:
    showing = Showing(
        id=id,
        cinema_id=cinema_id,
        film_id=film_id,
        start_time=datetime(2026, 2, 20, 19, 30, tzinfo=LONDON_TZ),
        booking_url=None,
        screen_name=None,
        format_tags=None,
        price=None,
    )
    showing.cinema = make_cinema(cinema_id)
    return showing


def make_db(get_side_effect=None, execute_result=None, flush_side_effect=None):
    async def _override():
        db = AsyncMock()
        if get_side_effect is not None:
            db.get = AsyncMock(side_effect=get_side_effect)
        db.execute = AsyncMock(return_value=execute_result or MagicMock())
        if flush_side_effect is not None:
            db.flush = AsyncMock(side_effect=flush_side_effect)
        db.add = MagicMock(side_effect=lambda obj: setattr(obj, "id", 1))

        async def _refresh(obj: object) -> None:
            if getattr(obj, "created_at", None) is None:
                setattr(obj, "created_at", datetime(2026, 2, 20, 12, 0, tzinfo=LONDON_TZ))

        db.refresh = AsyncMock(side_effect=_refresh)
        db.delete = AsyncMock()
        yield db

    return _override


@pytest.fixture
def app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.include_router(watch_logs.router)
    fastapi_app.dependency_overrides[get_current_user] = lambda: USER
    return fastapi_app


# ---------------------------------------------------------------------------
# POST /watch-logs
# ---------------------------------------------------------------------------


async def test_create_manual_watch_log(app: FastAPI) -> None:
    film = make_film()
    app.dependency_overrides[get_db] = make_db(get_side_effect=[film])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/watch-logs",
                json={"film_id": "nosferatu-2024", "watched_date": "2026-02-20", "rating": 4.5},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    data = response.json()
    assert data["film_id"] == "nosferatu-2024"
    assert data["showing_id"] is None
    assert data["watched_date"] == "2026-02-20"
    assert data["rating"] == 4.5


async def test_create_manual_watch_log_requires_film_id_and_date() -> None:
    from pydantic import ValidationError

    from cinescout.schemas.watch_log import WatchLogCreate

    with pytest.raises(ValidationError):
        WatchLogCreate()

    with pytest.raises(ValidationError):
        WatchLogCreate(film_id="nosferatu-2024")  # missing watched_date


async def test_create_showing_watch_log_autofills_film_and_date(app: FastAPI) -> None:
    showing = make_showing()
    app.dependency_overrides[get_db] = make_db(get_side_effect=[showing])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Client tries to pass a different film_id/watched_date — must be ignored.
            response = await client.post(
                "/watch-logs",
                json={
                    "showing_id": 1,
                    "film_id": "should-be-ignored",
                    "watched_date": "1999-01-01",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    data = response.json()
    assert data["film_id"] == "nosferatu-2024"
    assert data["showing_id"] == 1
    assert data["watched_date"] == "2026-02-20"


async def test_create_watch_log_404_when_showing_not_found(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = make_db(get_side_effect=[None])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/watch-logs", json={"showing_id": 999})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


async def test_create_watch_log_404_when_film_not_found_for_manual_entry(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = make_db(get_side_effect=[None])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/watch-logs", json={"film_id": "unknown-film", "watched_date": "2026-02-20"}
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


async def test_create_watch_log_409_on_duplicate_showing(app: FastAPI) -> None:
    showing = make_showing()
    app.dependency_overrides[get_db] = make_db(
        get_side_effect=[showing],
        flush_side_effect=IntegrityError("duplicate", {}, Exception()),
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/watch-logs", json={"showing_id": 1})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409


async def test_create_watch_log_rejects_rating_outside_half_star_scale(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/watch-logs",
                json={"film_id": "x", "watched_date": "2026-02-20", "rating": 4.3},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /watch-logs
# ---------------------------------------------------------------------------


async def test_list_watch_logs_scopes_query_to_current_user(app: FastAPI) -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/watch-logs")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET/DELETE /watch-logs/{id}
# ---------------------------------------------------------------------------


async def test_get_watch_log_404_when_not_owned_by_user(app: FastAPI) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/watch-logs/42")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


async def test_delete_watch_log_returns_204(app: FastAPI) -> None:
    from cinescout.models import WatchLog

    log = WatchLog(id=1, user_id=1, film_id="x", watched_date=date(2026, 2, 20))
    result = MagicMock()
    result.scalar_one_or_none.return_value = log
    app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/watch-logs/1")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 204


async def test_delete_watch_log_404_when_not_found_or_not_owned(app: FastAPI) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/watch-logs/999")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
