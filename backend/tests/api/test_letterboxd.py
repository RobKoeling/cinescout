"""Tests for the Letterboxd link/import API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cinescout.api.dependencies import get_current_user
from cinescout.api.routes import letterboxd
from cinescout.database import get_db
from cinescout.models import Film, User
from cinescout.services.letterboxd_client import LetterboxdEntry

USER = User(id=1, username="alice", password_hash="x", is_active=True)


def make_db(execute_result=None):
    async def _override():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=execute_result or MagicMock())
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        yield db

    return _override


@pytest.fixture
def app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.include_router(letterboxd.router)
    fastapi_app.dependency_overrides[get_current_user] = lambda: USER
    return fastapi_app


def make_entry(
    tmdb_id: int | None = 784524,
    watched_date=None,
    rating: float | None = 3.5,
) -> LetterboxdEntry:
    from datetime import date as date_cls

    return LetterboxdEntry(
        film_title="Magazine Dreams",
        film_year=2023,
        watched_date=watched_date or date_cls(2026, 9, 4),
        rating=rating,
        rewatch=False,
        tmdb_id=tmdb_id,
        letterboxd_url="https://letterboxd.com/testuser/film/magazine-dreams/",
    )


# ---------------------------------------------------------------------------
# POST /letterboxd/link
# ---------------------------------------------------------------------------


async def test_link_sets_username_when_profile_confirmed(app: FastAPI) -> None:
    USER.letterboxd_username = None
    app.dependency_overrides[get_db] = make_db()
    with patch(
        "cinescout.api.routes.letterboxd.LetterboxdClient.profile_exists",
        AsyncMock(return_value=True),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/letterboxd/link", json={"letterboxd_username": "testuser"}
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["letterboxd_username"] == "testuser"


async def test_link_allows_linking_when_profile_check_fails_soft(app: FastAPI) -> None:
    USER.letterboxd_username = None
    app.dependency_overrides[get_db] = make_db()
    with patch(
        "cinescout.api.routes.letterboxd.LetterboxdClient.profile_exists",
        AsyncMock(return_value=None),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/letterboxd/link", json={"letterboxd_username": "testuser"}
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


async def test_link_rejects_confirmed_nonexistent_profile(app: FastAPI) -> None:
    app.dependency_overrides[get_db] = make_db()
    with patch(
        "cinescout.api.routes.letterboxd.LetterboxdClient.profile_exists",
        AsyncMock(return_value=False),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/letterboxd/link", json={"letterboxd_username": "nobody"}
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /letterboxd/link
# ---------------------------------------------------------------------------


async def test_unlink_clears_username(app: FastAPI) -> None:
    USER.letterboxd_username = "testuser"
    app.dependency_overrides[get_db] = make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/letterboxd/link")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["letterboxd_username"] is None


# ---------------------------------------------------------------------------
# POST /letterboxd/import
# ---------------------------------------------------------------------------


async def test_import_requires_linked_account(app: FastAPI) -> None:
    USER.letterboxd_username = None
    app.dependency_overrides[get_db] = make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/letterboxd/import")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400


async def test_import_returns_502_when_fetch_diary_fails(app: FastAPI) -> None:
    USER.letterboxd_username = "testuser"
    app.dependency_overrides[get_db] = make_db()
    with patch(
        "cinescout.api.routes.letterboxd.LetterboxdClient.fetch_diary", AsyncMock(return_value=None)
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/letterboxd/import")
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 502


async def test_import_creates_watch_logs_and_counts_imported(app: FastAPI) -> None:
    USER.letterboxd_username = "testuser"
    film = Film(id="magazine-dreams-2023", title="Magazine Dreams", year=2023, tmdb_id=784524)

    no_dup_result = MagicMock()
    no_dup_result.scalar_one_or_none.return_value = None
    app.dependency_overrides[get_db] = make_db(execute_result=no_dup_result)

    with (
        patch(
            "cinescout.api.routes.letterboxd.LetterboxdClient.fetch_diary",
            AsyncMock(return_value=[make_entry()]),
        ),
        patch(
            "cinescout.api.routes.letterboxd.FilmMatcher.match_by_tmdb_id",
            AsyncMock(return_value=film),
        ),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/letterboxd/import")
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["entries_found"] == 1
    assert data["entries_imported"] == 1
    assert data["entries_skipped_duplicate"] == 0
    assert data["entries_unmatched"] == 0


async def test_import_skips_duplicate_entries(app: FastAPI) -> None:
    from cinescout.models import WatchLog

    USER.letterboxd_username = "testuser"
    film = Film(id="magazine-dreams-2023", title="Magazine Dreams", year=2023, tmdb_id=784524)
    existing_log = WatchLog(id=1, user_id=1, film_id=film.id, watched_date=make_entry().watched_date)

    dup_result = MagicMock()
    dup_result.scalar_one_or_none.return_value = existing_log
    app.dependency_overrides[get_db] = make_db(execute_result=dup_result)

    with (
        patch(
            "cinescout.api.routes.letterboxd.LetterboxdClient.fetch_diary",
            AsyncMock(return_value=[make_entry()]),
        ),
        patch(
            "cinescout.api.routes.letterboxd.FilmMatcher.match_by_tmdb_id",
            AsyncMock(return_value=film),
        ),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/letterboxd/import")
        finally:
            app.dependency_overrides.pop(get_db, None)

    data = response.json()
    assert data["entries_skipped_duplicate"] == 1
    assert data["entries_imported"] == 0


async def test_import_counts_unmatched_entries_without_tmdb_id(app: FastAPI) -> None:
    USER.letterboxd_username = "testuser"
    app.dependency_overrides[get_db] = make_db()

    with patch(
        "cinescout.api.routes.letterboxd.LetterboxdClient.fetch_diary",
        AsyncMock(return_value=[make_entry(tmdb_id=None)]),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/letterboxd/import")
        finally:
            app.dependency_overrides.pop(get_db, None)

    data = response.json()
    assert data["entries_unmatched"] == 1
    assert data["entries_imported"] == 0
