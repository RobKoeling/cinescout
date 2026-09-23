"""Tests for the watchlist import/list/upcoming API endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cinescout.api.dependencies import get_current_user
from cinescout.api.routes import watchlist
from cinescout.database import get_db
from cinescout.models import Cinema, Film, Showing, User, WatchlistItem
from cinescout.services.letterboxd_client import WatchlistEntry

USER = User(id=1, username="alice", password_hash="x", is_active=True)


def make_db(execute_result=None):
    async def _override():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=execute_result if execute_result is not None else MagicMock())
        db.flush = AsyncMock()
        db.delete = AsyncMock()
        db.add = MagicMock()
        yield db

    return _override


@pytest.fixture
def app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.include_router(watchlist.router)
    fastapi_app.dependency_overrides[get_current_user] = lambda: USER
    return fastapi_app


# ---------------------------------------------------------------------------
# POST /watchlist/import
# ---------------------------------------------------------------------------


async def test_import_requires_linked_account(app: FastAPI) -> None:
    USER.letterboxd_username = None
    app.dependency_overrides[get_db] = make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/watchlist/import")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400


async def test_import_returns_502_when_fetch_fails(app: FastAPI) -> None:
    USER.letterboxd_username = "testuser"
    app.dependency_overrides[get_db] = make_db()
    with patch(
        "cinescout.api.routes.watchlist.LetterboxdClient.fetch_watchlist", AsyncMock(return_value=None)
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/watchlist/import")
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 502


async def test_import_adds_new_films_and_removes_stale_ones(app: FastAPI) -> None:
    USER.letterboxd_username = "testuser"
    new_film = Film(id="coyote-vs-acme-2026", title="Coyote vs. Acme", year=2026)
    stale_item = WatchlistItem(id=1, user_id=1, film_id="some-old-film-2020")

    existing_result = MagicMock()
    existing_result.scalars.return_value.all.return_value = [stale_item]
    app.dependency_overrides[get_db] = make_db(execute_result=existing_result)

    with (
        patch(
            "cinescout.api.routes.watchlist.LetterboxdClient.fetch_watchlist",
            AsyncMock(return_value=[WatchlistEntry(title="Coyote vs. Acme", year=2026)]),
        ),
        patch(
            "cinescout.api.routes.watchlist.FilmMatcher.match_or_create_film",
            AsyncMock(return_value=new_film),
        ),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/watchlist/import")
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["entries_found"] == 1
    assert data["entries_imported"] == 1
    assert data["entries_removed"] == 1


# ---------------------------------------------------------------------------
# GET /watchlist/upcoming
# ---------------------------------------------------------------------------


async def test_upcoming_returns_future_showings_for_watchlisted_films(app: FastAPI) -> None:
    film = Film(id="clayface-2026", title="Clayface", year=2026)
    cinema = Cinema(
        id="test-cinema",
        name="Test Cinema",
        city="London",
        address="1 Test St",
        postcode="AB1 2CD",
        scraper_type="test",
        has_online_booking=True,
        supports_availability_check=False,
    )
    showing = Showing(
        id=1,
        cinema_id=cinema.id,
        film_id=film.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=3),
    )
    showing.film = film
    showing.cinema = cinema

    result = MagicMock()
    result.scalars.return_value.all.return_value = [showing]
    app.dependency_overrides[get_db] = make_db(execute_result=result)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/watchlist/upcoming")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["film"]["title"] == "Clayface"
    assert data[0]["cinema"]["name"] == "Test Cinema"
