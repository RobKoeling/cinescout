"""Tests for the cinemas API endpoint."""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cinescout.database import get_db
from cinescout.models.cinema import Cinema


def make_cinema(id: str, name: str, city: str = "london") -> Cinema:
    return Cinema(
        id=id,
        name=name,
        city=city,
        address="123 Test Street",
        postcode="W1A 1AA",
        latitude=51.5,
        longitude=-0.1,
        website="https://example.com",
        scraper_type="test",
        scraper_config=None,
        has_online_booking=True,
        supports_availability_check=False,
    )


async def test_returns_cinemas_for_default_city(test_app: FastAPI) -> None:
    bfi = make_cinema("bfi-southbank", "BFI Southbank")
    curzon = make_cinema("curzon-soho", "Curzon Soho")

    async def override() -> AsyncMock:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [bfi, curzon]
        db.execute = AsyncMock(return_value=result)
        yield db

    test_app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/cinemas")
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {c["name"] for c in data}
    assert "BFI Southbank" in names
    assert "Curzon Soho" in names


async def test_filters_by_city_query_param(test_app: FastAPI) -> None:
    async def override() -> AsyncMock:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result)
        yield db

    test_app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/cinemas?city=paris")
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


async def test_cinema_response_includes_required_fields(test_app: FastAPI) -> None:
    cinema = make_cinema("bfi-southbank", "BFI Southbank")

    async def override() -> AsyncMock:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [cinema]
        db.execute = AsyncMock(return_value=result)
        yield db

    test_app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/cinemas")
    finally:
        test_app.dependency_overrides.clear()

    c = response.json()[0]
    assert c["id"] == "bfi-southbank"
    assert c["name"] == "BFI Southbank"
    assert c["city"] == "london"
    assert c["postcode"] == "W1A 1AA"
    assert c["has_online_booking"] is True
    assert c["supports_availability_check"] is False
