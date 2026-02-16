"""Unit tests for the Regent Street Cinema scraper."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cinescout.scrapers.regent_street import BASE_URL, RegentStreetScraper

LONDON_TZ = ZoneInfo("Europe/London")
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "regent_street"


@pytest.fixture
def scraper() -> RegentStreetScraper:
    return RegentStreetScraper()


@pytest.fixture
def dates_data() -> dict:
    return json.loads((FIXTURE_DIR / "dates.json").read_text())


@pytest.fixture
def showings_data() -> dict:
    return json.loads((FIXTURE_DIR / "showings.json").read_text())


# ---------------------------------------------------------------------------
# _parse_showing — pure parsing, no HTTP
# ---------------------------------------------------------------------------


class TestRegentStreetParseShowing:
    def setup_method(self) -> None:
        self.scraper = RegentStreetScraper()

    def test_parses_basic_showing(self) -> None:
        item = {
            "id": "12345",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "Nosferatu", "urlSlug": "nosferatu"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is not None
        assert showing.title == "Nosferatu"
        assert showing.start_time == datetime(2026, 2, 20, 18, 30, tzinfo=LONDON_TZ)

    def test_start_time_is_timezone_aware(self) -> None:
        item = {
            "id": "12345",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "Nosferatu", "urlSlug": "nosferatu"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is not None
        assert showing.start_time.tzinfo is not None

    def test_builds_booking_url_with_url_slug(self) -> None:
        item = {
            "id": "12345",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "Nosferatu", "urlSlug": "nosferatu"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is not None
        assert showing.booking_url == f"{BASE_URL}/checkout/showing/nosferatu/12345/"

    def test_builds_booking_url_without_url_slug(self) -> None:
        item = {
            "id": "12345",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "Nosferatu", "urlSlug": ""},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is not None
        assert showing.booking_url == f"{BASE_URL}/checkout/showing/12345/"

    def test_returns_none_when_title_missing(self) -> None:
        item = {
            "id": "12345",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "", "urlSlug": "nosferatu"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is None

    def test_returns_none_when_id_missing(self) -> None:
        item = {
            "id": "",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "Nosferatu", "urlSlug": "nosferatu"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is None

    def test_returns_none_when_time_missing(self) -> None:
        item = {
            "id": "12345",
            "time": "",
            "movie": {"name": "Nosferatu", "urlSlug": "nosferatu"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is None

    def test_returns_none_for_very_short_title(self) -> None:
        item = {
            "id": "12345",
            "time": "2026-02-20T18:30:00",
            "movie": {"name": "X", "urlSlug": "x"},
        }
        showing = self.scraper._parse_showing(item)
        assert showing is None


# ---------------------------------------------------------------------------
# get_showings — mocked HTTP
# ---------------------------------------------------------------------------


class TestRegentStreetGetShowings:
    async def test_returns_showings_filtered_to_date_range(
        self,
        scraper: RegentStreetScraper,
        dates_data: dict,
        showings_data: dict,
    ) -> None:
        # dates fixture: ["2026-02-20", "2026-02-21", "2026-02-28"]
        # range: Feb 20 only → 1 date fetched → 2 showings from showings fixture

        async def mock_post(url: str, **kwargs: object) -> MagicMock:
            r = MagicMock()
            r.status_code = 200
            body = kwargs.get("json", {})
            query = body.get("query", "")
            if "datesWithShowing" in query:
                r.json = MagicMock(return_value=dates_data)
            else:
                r.json = MagicMock(return_value=showings_data)
            r.raise_for_status = MagicMock()
            return r

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 2, 20), date(2026, 2, 20))

        assert len(showings) == 2
        titles = {s.title for s in showings}
        assert "Nosferatu" in titles
        assert "The Substance" in titles
        assert all(s.start_time.tzinfo is not None for s in showings)

    async def test_returns_empty_list_when_no_dates_in_range(
        self,
        scraper: RegentStreetScraper,
        dates_data: dict,
    ) -> None:
        # dates fixture has Feb 20, 21, 28 — request a range that doesn't overlap

        async def mock_post(url: str, **kwargs: object) -> MagicMock:
            r = MagicMock()
            r.status_code = 200
            r.json = MagicMock(return_value=dates_data)
            r.raise_for_status = MagicMock()
            return r

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 3, 1), date(2026, 3, 7))

        assert showings == []

    async def test_returns_empty_list_on_http_error(self, scraper: RegentStreetScraper) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 2, 20), date(2026, 2, 21))

        assert showings == []
