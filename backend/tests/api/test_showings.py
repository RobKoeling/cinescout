"""Tests for the showings API endpoint."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cinescout.database import get_db
from cinescout.models.cinema import Cinema
from cinescout.models.film import Film
from cinescout.models.showing import Showing

LONDON_TZ = ZoneInfo("Europe/London")


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def make_cinema(id: str = "bfi-southbank", name: str = "BFI Southbank") -> Cinema:
    return Cinema(
        id=id,
        name=name,
        city="london",
        address="Belvedere Road",
        postcode="SE1 8XT",
        latitude=51.5065,
        longitude=-0.1150,
        website="https://bfi.org.uk",
        scraper_type="bfi",
        scraper_config=None,
        has_online_booking=True,
        supports_availability_check=False,
    )


def make_film(
    id: str = "nosferatu-2024",
    title: str = "Nosferatu",
    year: int = 2024,
) -> Film:
    return Film(
        id=id,
        title=title,
        year=year,
        directors=None,
        countries=None,
        overview="A horror film.",
        poster_path="/nosferatu.jpg",
        runtime=132,
        tmdb_id=12345,
    )


def make_showing(
    cinema: Cinema,
    film: Film,
    showing_id: int = 1,
    start_time: datetime | None = None,
) -> Showing:
    if start_time is None:
        start_time = datetime(2026, 2, 20, 18, 30, tzinfo=LONDON_TZ)
    s = Showing(
        id=showing_id,
        cinema_id=cinema.id,
        film_id=film.id,
        start_time=start_time,
        booking_url=f"https://example.com/book/{showing_id}",
        screen_name="Screen 1",
        format_tags=None,
        price=None,
    )
    s.film = film
    s.cinema = cinema
    return s


def make_db_override(showings: list[Showing]):
    async def override():
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = showings
        db.execute = AsyncMock(return_value=result)
        yield db

    return override


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_returns_showings_grouped_by_film(test_app: FastAPI) -> None:
    cinema = make_cinema()
    film = make_film()
    showing = make_showing(cinema, film)

    test_app.dependency_overrides[get_db] = make_db_override([showing])
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/showings?date=2026-02-20")
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_films"] == 1
    assert data["total_showings"] == 1
    assert data["films"][0]["film"]["title"] == "Nosferatu"
    assert data["films"][0]["cinemas"][0]["cinema"]["name"] == "BFI Southbank"


async def test_returns_empty_when_no_showings(test_app: FastAPI) -> None:
    test_app.dependency_overrides[get_db] = make_db_override([])
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/showings?date=2026-02-20")
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_films"] == 0
    assert data["total_showings"] == 0
    assert data["films"] == []


async def test_films_sorted_by_showing_count_descending(test_app: FastAPI) -> None:
    cinema = make_cinema()
    film_a = make_film(id="film-a", title="Film A")
    film_b = make_film(id="film-b", title="Film B")

    # Film B has 2 showings, Film A has 1 — Film B should appear first
    showings = [
        make_showing(cinema, film_a, showing_id=1, start_time=datetime(2026, 2, 20, 14, 0, tzinfo=LONDON_TZ)),
        make_showing(cinema, film_b, showing_id=2, start_time=datetime(2026, 2, 20, 16, 0, tzinfo=LONDON_TZ)),
        make_showing(cinema, film_b, showing_id=3, start_time=datetime(2026, 2, 20, 18, 0, tzinfo=LONDON_TZ)),
    ]

    test_app.dependency_overrides[get_db] = make_db_override(showings)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/showings?date=2026-02-20")
    finally:
        test_app.dependency_overrides.clear()

    data = response.json()
    assert data["total_films"] == 2
    assert data["total_showings"] == 3
    assert data["films"][0]["film"]["title"] == "Film B"
    assert data["films"][0]["film"]["showing_count"] == 2
    assert data["films"][1]["film"]["title"] == "Film A"


async def test_query_params_reflected_in_response(test_app: FastAPI) -> None:
    test_app.dependency_overrides[get_db] = make_db_override([])
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/showings?date=2026-02-20&time_from=18:00&time_to=21:00"
            )
    finally:
        test_app.dependency_overrides.clear()

    query = response.json()["query"]
    assert query["date"] == "2026-02-20"
    assert query["time_from"] == "18:00:00"
    assert query["time_to"] == "21:00:00"


async def test_missing_date_returns_422(test_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/showings")

    assert response.status_code == 422


async def test_showing_response_includes_booking_url_and_screen(test_app: FastAPI) -> None:
    cinema = make_cinema()
    film = make_film()
    showing = make_showing(cinema, film)
    showing.screen_name = "NFT1"
    showing.booking_url = "https://bfi.org.uk/book/99"

    test_app.dependency_overrides[get_db] = make_db_override([showing])
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/showings?date=2026-02-20")
    finally:
        test_app.dependency_overrides.clear()

    time_entry = response.json()["films"][0]["cinemas"][0]["times"][0]
    assert time_entry["booking_url"] == "https://bfi.org.uk/book/99"
    assert time_entry["screen_name"] == "NFT1"
