"""Tests for the admin scrape API endpoints."""

from contextlib import asynccontextmanager
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cinescout.api.routes import admin
from cinescout.database import get_db
from cinescout.models.cinema import Cinema
from cinescout.models.film import Film
from cinescout.models.showing import Showing
from cinescout.scrapers.models import RawShowing

LONDON_TZ = ZoneInfo("Europe/London")

SCRAPE_PAYLOAD = {
    "cinema_ids": ["bfi-southbank"],
    "date_from": "2026-02-20",
    "date_to": "2026-02-20",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cinema(
    id: str = "bfi-southbank",
    name: str = "BFI Southbank",
    scraper_type: str = "bfi",
) -> Cinema:
    return Cinema(
        id=id,
        name=name,
        city="london",
        address="Belvedere Road",
        postcode="SE1 8XT",
        latitude=51.5065,
        longitude=-0.1150,
        website="https://bfi.org.uk",
        scraper_type=scraper_type,
        scraper_config=None,
        has_online_booking=True,
        supports_availability_check=False,
    )


def make_film(id: str = "nosferatu-2024", tmdb_id: int | None = 12345) -> Film:
    return Film(
        id=id,
        title="Nosferatu",
        year=2024,
        directors=None,
        countries=None,
        overview="A horror film.",
        poster_path="/nosferatu.jpg",
        runtime=132,
        tmdb_id=tmdb_id,
    )


def make_raw_showing(title: str = "Nosferatu") -> RawShowing:
    return RawShowing(
        title=title,
        start_time=datetime(2026, 2, 20, 18, 30, tzinfo=LONDON_TZ),
        booking_url="https://bfi.org.uk/book/1",
        screen_name="NFT1",
        format_tags=None,
        price=None,
    )


def make_nested_ctx():
    @asynccontextmanager
    async def _ctx():
        yield

    return _ctx()


def make_db(cinema: Cinema | None = None, execute_side_effects: list | None = None):
    """Return an async generator that yields a mock db session."""

    async def _override():
        db = AsyncMock()
        db.begin_nested = MagicMock(side_effect=lambda: make_nested_ctx())

        if execute_side_effects is not None:
            db.execute = AsyncMock(side_effect=execute_side_effects)
        else:
            # Default: cinema query returns [cinema], all other queries return None
            cinema_result = MagicMock()
            cinema_result.scalars.return_value.all.return_value = (
                [cinema] if cinema else []
            )

            empty_result = MagicMock()
            empty_result.scalar_one_or_none.return_value = None

            db.execute = AsyncMock(side_effect=[cinema_result, empty_result, empty_result])

        yield db

    return _override


@pytest.fixture
def admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin.router)
    return app


# ---------------------------------------------------------------------------
# POST /admin/scrape — happy path
# ---------------------------------------------------------------------------


async def test_scrape_returns_404_when_no_cinemas_found(admin_app: FastAPI) -> None:
    admin_app.dependency_overrides[get_db] = make_db(cinema=None)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
    finally:
        admin_app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "No cinemas found" in response.json()["detail"]


async def test_scrape_returns_error_result_when_no_scraper(admin_app: FastAPI) -> None:
    cinema = make_cinema(scraper_type="nonexistent")
    admin_app.dependency_overrides[get_db] = make_db(cinema=cinema)

    with patch("cinescout.api.routes.admin.get_scraper", return_value=None):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_showings"] == 0
    result = data["results"][0]
    assert result["success"] is False
    assert "No scraper found" in result["error"]


async def test_scrape_creates_new_showing(admin_app: FastAPI) -> None:
    cinema = make_cinema()
    film = make_film()
    raw = make_raw_showing()

    # DB execute calls: cinema query, then existing-showing check, placeholder check
    cinema_result = MagicMock()
    cinema_result.scalars.return_value.all.return_value = [cinema]
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None

    admin_app.dependency_overrides[get_db] = make_db(
        execute_side_effects=[cinema_result, empty, empty]
    )

    mock_scraper = AsyncMock()
    mock_scraper.get_showings = AsyncMock(return_value=[raw])

    mock_matcher = AsyncMock()
    mock_matcher.match_or_create_film = AsyncMock(return_value=film)

    with (
        patch("cinescout.api.routes.admin.get_scraper", return_value=mock_scraper),
        patch("cinescout.api.routes.admin.FilmMatcher", return_value=mock_matcher),
        patch("cinescout.api.routes.admin.TMDbClient", return_value=AsyncMock()),
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_showings"] == 1
    result = data["results"][0]
    assert result["success"] is True
    assert result["showings_created"] == 1
    assert result["cinema_id"] == "bfi-southbank"


async def test_scrape_updates_existing_showing(admin_app: FastAPI) -> None:
    cinema = make_cinema()
    film = make_film()
    raw = make_raw_showing()

    existing_showing = MagicMock(spec=Showing)
    existing_showing.film_id = film.id

    cinema_result = MagicMock()
    cinema_result.scalars.return_value.all.return_value = [cinema]
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_showing

    admin_app.dependency_overrides[get_db] = make_db(
        execute_side_effects=[cinema_result, existing_result]
    )

    mock_scraper = AsyncMock()
    mock_scraper.get_showings = AsyncMock(return_value=[raw])

    mock_matcher = AsyncMock()
    mock_matcher.match_or_create_film = AsyncMock(return_value=film)

    with (
        patch("cinescout.api.routes.admin.get_scraper", return_value=mock_scraper),
        patch("cinescout.api.routes.admin.FilmMatcher", return_value=mock_matcher),
        patch("cinescout.api.routes.admin.TMDbClient", return_value=AsyncMock()),
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    data = response.json()
    assert data["total_showings"] == 0  # updated, not created
    assert data["results"][0]["success"] is True
    # booking_url was updated on the existing showing
    assert existing_showing.booking_url == raw.booking_url
    assert existing_showing.raw_title == raw.title


async def test_scrape_migrates_placeholder_showing(admin_app: FastAPI) -> None:
    """When a real TMDb film is matched and a placeholder showing exists at the
    same time/cinema, it should be migrated rather than a new showing created."""
    cinema = make_cinema()
    real_film = make_film(tmdb_id=12345)
    raw = make_raw_showing()

    placeholder_showing = MagicMock(spec=Showing)
    placeholder_showing.film_id = "placeholder-film"

    cinema_result = MagicMock()
    cinema_result.scalars.return_value.all.return_value = [cinema]
    # existing showing check returns None (real film doesn't have it yet)
    no_existing = MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    # placeholder check returns the placeholder showing
    placeholder_result = MagicMock()
    placeholder_result.scalar_one_or_none.return_value = placeholder_showing

    admin_app.dependency_overrides[get_db] = make_db(
        execute_side_effects=[cinema_result, no_existing, placeholder_result]
    )

    mock_scraper = AsyncMock()
    mock_scraper.get_showings = AsyncMock(return_value=[raw])

    mock_matcher = AsyncMock()
    mock_matcher.match_or_create_film = AsyncMock(return_value=real_film)

    with (
        patch("cinescout.api.routes.admin.get_scraper", return_value=mock_scraper),
        patch("cinescout.api.routes.admin.FilmMatcher", return_value=mock_matcher),
        patch("cinescout.api.routes.admin.TMDbClient", return_value=AsyncMock()),
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    data = response.json()
    # Placeholder was migrated, so no new showing created
    assert data["total_showings"] == 0
    assert data["results"][0]["success"] is True
    # The placeholder showing's film_id was updated to the real film
    assert placeholder_showing.film_id == real_film.id


async def test_scrape_continues_after_scraper_exception(admin_app: FastAPI) -> None:
    cinema = make_cinema()

    cinema_result = MagicMock()
    cinema_result.scalars.return_value.all.return_value = [cinema]

    admin_app.dependency_overrides[get_db] = make_db(
        execute_side_effects=[cinema_result]
    )

    mock_scraper = AsyncMock()
    mock_scraper.get_showings = AsyncMock(side_effect=Exception("Site unreachable"))

    with (
        patch("cinescout.api.routes.admin.get_scraper", return_value=mock_scraper),
        patch("cinescout.api.routes.admin.TMDbClient", return_value=AsyncMock()),
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    result = data["results"][0]
    assert result["success"] is False
    assert "Site unreachable" in result["error"]
    assert data["total_showings"] == 0


async def test_scrape_skips_duplicate_showings(admin_app: FastAPI) -> None:
    """IntegrityError during showing flush is silently skipped."""
    from sqlalchemy.exc import IntegrityError

    cinema = make_cinema()
    film = make_film()
    raw = make_raw_showing()

    cinema_result = MagicMock()
    cinema_result.scalars.return_value.all.return_value = [cinema]
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None

    admin_app.dependency_overrides[get_db] = make_db(
        execute_side_effects=[cinema_result, empty, empty]
    )

    mock_scraper = AsyncMock()
    mock_scraper.get_showings = AsyncMock(return_value=[raw])

    mock_matcher = AsyncMock()
    mock_matcher.match_or_create_film = AsyncMock(return_value=film)

    # Simulate IntegrityError raised during the savepoint flush
    def raise_integrity(*args, **kwargs):
        raise IntegrityError("duplicate", {}, Exception())

    def begin_nested_raises():
        @asynccontextmanager
        async def _ctx():
            raise_integrity()
            yield

        return _ctx()

    with (
        patch("cinescout.api.routes.admin.get_scraper", return_value=mock_scraper),
        patch("cinescout.api.routes.admin.FilmMatcher", return_value=mock_matcher),
        patch("cinescout.api.routes.admin.TMDbClient", return_value=AsyncMock()),
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                # Override begin_nested after the dependency override is set
                db_override = admin_app.dependency_overrides[get_db]

                async def patched_override():
                    async for db in db_override():
                        db.begin_nested = MagicMock(side_effect=lambda: begin_nested_raises())
                        yield db

                admin_app.dependency_overrides[get_db] = patched_override
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    data = response.json()
    # IntegrityError is caught — showing skipped but overall still success
    assert data["results"][0]["success"] is True
    assert data["total_showings"] == 0


# ---------------------------------------------------------------------------
# POST /admin/scrape-all
# ---------------------------------------------------------------------------


async def test_scrape_all_returns_started(admin_app: FastAPI) -> None:
    with patch("cinescout.api.routes.admin.run_scrape_all"):
        async with AsyncClient(
            transport=ASGITransport(app=admin_app), base_url="http://test"
        ) as client:
            response = await client.post("/admin/scrape-all")

    assert response.status_code == 200
    assert response.json() == {"status": "started"}


async def test_scrape_response_shape(admin_app: FastAPI) -> None:
    """Response always has status, results, and total_showings."""
    cinema = make_cinema()
    film = make_film()
    raw = make_raw_showing()

    cinema_result = MagicMock()
    cinema_result.scalars.return_value.all.return_value = [cinema]
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None

    admin_app.dependency_overrides[get_db] = make_db(
        execute_side_effects=[cinema_result, empty, empty]
    )

    mock_scraper = AsyncMock()
    mock_scraper.get_showings = AsyncMock(return_value=[raw])

    mock_matcher = AsyncMock()
    mock_matcher.match_or_create_film = AsyncMock(return_value=film)

    with (
        patch("cinescout.api.routes.admin.get_scraper", return_value=mock_scraper),
        patch("cinescout.api.routes.admin.FilmMatcher", return_value=mock_matcher),
        patch("cinescout.api.routes.admin.TMDbClient", return_value=AsyncMock()),
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=admin_app), base_url="http://test"
            ) as client:
                response = await client.post("/admin/scrape", json=SCRAPE_PAYLOAD)
        finally:
            admin_app.dependency_overrides.clear()

    data = response.json()
    assert "status" in data
    assert "results" in data
    assert "total_showings" in data
    result = data["results"][0]
    assert "cinema_id" in result
    assert "cinema_name" in result
    assert "success" in result
    assert "showings_created" in result
