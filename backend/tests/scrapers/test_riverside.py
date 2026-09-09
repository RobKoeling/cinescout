"""Unit tests for the Riverside Studios scraper."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cinescout.scrapers.riverside import RiversideScraper

LONDON_TZ = ZoneInfo("Europe/London")
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "riverside"


@pytest.fixture
def scraper() -> RiversideScraper:
    return RiversideScraper()


@pytest.fixture
def fixture_events() -> list[dict]:
    return json.loads((FIXTURE_DIR / "events.json").read_text())


@pytest.fixture
def fixture_instances() -> list[dict]:
    return json.loads((FIXTURE_DIR / "instances.json").read_text())


# ---------------------------------------------------------------------------
# _fetch_cinema_events — mocked HTTP
# ---------------------------------------------------------------------------


class TestFetchCinemaEvents:
    async def test_returns_event_map_from_response(
        self, scraper: RiversideScraper, fixture_events: list[dict]
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=fixture_events)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        event_map = await scraper._fetch_cinema_events(mock_client)

        assert len(event_map) == 3
        # Arco should be present
        arco_entry = next(
            (v for v in event_map.values() if v["title"] == "Arco"), None
        )
        assert arco_entry is not None
        assert arco_entry["year"] == 2026

    async def test_returns_empty_dict_on_non_200(
        self, scraper: RiversideScraper
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        event_map = await scraper._fetch_cinema_events(mock_client)

        assert event_map == {}

    async def test_normalises_title(
        self, scraper: RiversideScraper, fixture_events: list[dict]
    ) -> None:
        events_with_suffix = fixture_events + [
            {
                "id": "TEST001",
                "name": "Adabana + Director Q&A",
                "attribute_YearOfRelease": "2024",
                "attribute_EventType": "Cinema",
            }
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=events_with_suffix)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        event_map = await scraper._fetch_cinema_events(mock_client)

        assert "TEST001" in event_map
        assert event_map["TEST001"]["title"] == "Adabana"

    async def test_handles_missing_year_gracefully(
        self, scraper: RiversideScraper
    ) -> None:
        events = [{"id": "X001", "name": "No Year Film", "attribute_YearOfRelease": ""}]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=events)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        event_map = await scraper._fetch_cinema_events(mock_client)

        assert event_map["X001"]["year"] is None


# ---------------------------------------------------------------------------
# _fetch_instances — mocked HTTP
# ---------------------------------------------------------------------------


class TestFetchInstances:
    async def test_filters_to_cinema_events_only(
        self,
        scraper: RiversideScraper,
        fixture_events: list[dict],
        fixture_instances: list[dict],
    ) -> None:
        # Build event_map from fixtures
        event_map = {
            e["id"]: {
                "title": e["name"],
                "year": int(e["attribute_YearOfRelease"]) if e.get("attribute_YearOfRelease") else None,
            }
            for e in fixture_events
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=fixture_instances)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        showings = await scraper._fetch_instances(
            mock_client, date(2026, 5, 23), date(2026, 5, 23), event_map
        )

        assert len(showings) == 5
        titles = {s.title for s in showings}
        assert "Arco" in titles
        assert "Star Wars: The Mandalorian and Grogu" in titles

    async def test_skips_cancelled_instances(
        self, scraper: RiversideScraper, fixture_instances: list[dict]
    ) -> None:
        event_map = {
            fixture_instances[0]["event"]["id"]: {"title": "Test Film", "year": 2026}
        }
        instances_with_cancelled = [
            {**fixture_instances[0], "cancelled": True},
            {**fixture_instances[0], "cancelled": False, "id": "OTHER_ID", "start": "2026-05-23T12:00:00"},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=instances_with_cancelled)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        showings = await scraper._fetch_instances(
            mock_client, date(2026, 5, 23), date(2026, 5, 23), event_map
        )

        assert len(showings) == 1

    async def test_showings_have_london_timezone(
        self,
        scraper: RiversideScraper,
        fixture_events: list[dict],
        fixture_instances: list[dict],
    ) -> None:
        event_map = {e["id"]: {"title": e["name"], "year": None} for e in fixture_events}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=fixture_instances)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        showings = await scraper._fetch_instances(
            mock_client, date(2026, 5, 23), date(2026, 5, 23), event_map
        )

        assert all(s.start_time.tzinfo is not None for s in showings)

    async def test_returns_empty_on_non_200(self, scraper: RiversideScraper) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        showings = await scraper._fetch_instances(
            mock_client, date(2026, 5, 23), date(2026, 5, 23), {}
        )

        assert showings == []


# ---------------------------------------------------------------------------
# get_showings — full integration with mocked HTTP
# ---------------------------------------------------------------------------


class TestGetShowings:
    async def test_returns_cinema_showings(
        self,
        scraper: RiversideScraper,
        fixture_events: list[dict],
        fixture_instances: list[dict],
    ) -> None:
        events_response = MagicMock()
        events_response.status_code = 200
        events_response.json = MagicMock(return_value=fixture_events)

        instances_response = MagicMock()
        instances_response.status_code = 200
        instances_response.json = MagicMock(return_value=fixture_instances)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[events_response, instances_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 5, 23), date(2026, 5, 23))

        assert len(showings) == 5
        assert all(s.start_time.tzinfo is not None for s in showings)

    async def test_returns_empty_list_on_exception(
        self, scraper: RiversideScraper
    ) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 5, 23), date(2026, 5, 23))

        assert showings == []

    async def test_returns_empty_list_when_no_cinema_events(
        self, scraper: RiversideScraper
    ) -> None:
        events_response = MagicMock()
        events_response.status_code = 200
        events_response.json = MagicMock(return_value=[])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=events_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 5, 23), date(2026, 5, 23))

        assert showings == []
