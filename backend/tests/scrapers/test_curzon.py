"""Unit tests for the Curzon Cinema scraper."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cinescout.scrapers.curzon import CurzonScraper

LONDON_TZ = ZoneInfo("Europe/London")
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "curzon"


@pytest.fixture
def scraper() -> CurzonScraper:
    return CurzonScraper(venue_id="SOH1")


@pytest.fixture
def venue_page_html() -> str:
    return (FIXTURE_DIR / "venue_page.html").read_text()


@pytest.fixture
def films_data() -> dict:
    return json.loads((FIXTURE_DIR / "films.json").read_text())


@pytest.fixture
def showtimes_data() -> dict:
    return json.loads((FIXTURE_DIR / "showtimes.json").read_text())


# ---------------------------------------------------------------------------
# _parse_showtime — pure parsing, no HTTP
# ---------------------------------------------------------------------------


class TestCurzonParseShowtime:
    def setup_method(self) -> None:
        self.scraper = CurzonScraper(venue_id="SOH1")
        self.film_map = {
            "FILM001": "The Grand Budapest Hotel",
            "FILM002": "Nosferatu",
        }
        self.day = date(2026, 2, 20)

    def test_parses_basic_showtime(self) -> None:
        st = {
            "id": "SHOW001",
            "filmId": "FILM001",
            "schedule": {"startsAt": "2026-02-20T14:30:00"},
        }
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)
        assert showing is not None
        assert showing.title == "The Grand Budapest Hotel"
        assert showing.start_time == datetime(2026, 2, 20, 14, 30, tzinfo=LONDON_TZ)

    def test_start_time_is_timezone_aware(self) -> None:
        st = {
            "id": "SHOW001",
            "filmId": "FILM001",
            "schedule": {"startsAt": "2026-02-20T18:30:00"},
        }
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)
        assert showing is not None
        assert showing.start_time.tzinfo is not None

    def test_builds_correct_booking_url(self) -> None:
        st = {
            "id": "SHOW999",
            "filmId": "FILM001",
            "schedule": {"startsAt": "2026-02-20T18:30:00"},
        }
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)
        assert showing is not None
        assert showing.booking_url == "https://www.curzon.com/ticketing/seats/SHOW999/"

    def test_falls_back_to_film_id_when_not_in_film_map(self) -> None:
        st = {
            "id": "SHOW003",
            "filmId": "UNKNOWN_FILM",
            "schedule": {"startsAt": "2026-02-20T21:00:00"},
        }
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)
        assert showing is not None
        assert showing.title == "UNKNOWN_FILM"

    def test_returns_none_when_film_id_missing(self) -> None:
        st = {"id": "SHOW001", "filmId": "", "schedule": {"startsAt": "2026-02-20T18:30:00"}}
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)
        assert showing is None

    def test_returns_none_when_starts_at_missing(self) -> None:
        st = {"id": "SHOW001", "filmId": "FILM001", "schedule": {}}
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)
        assert showing is None

    def test_returns_none_when_date_does_not_match_requested_day(self) -> None:
        # startsAt is on a different day than `day`
        st = {
            "id": "SHOW001",
            "filmId": "FILM001",
            "schedule": {"startsAt": "2026-02-21T00:30:00"},  # 00:30 on Feb 21
        }
        showing = self.scraper._parse_showtime(st, self.film_map, self.day)  # day is Feb 20
        assert showing is None


# ---------------------------------------------------------------------------
# get_showings — mocked HTTP
# ---------------------------------------------------------------------------


class TestCurzonGetShowings:
    async def test_returns_showings_from_mocked_api(
        self,
        scraper: CurzonScraper,
        venue_page_html: str,
        films_data: dict,
        showtimes_data: dict,
    ) -> None:
        # First httpx.AsyncClient: fetches the venue page for the auth token
        auth_response = MagicMock()
        auth_response.text = venue_page_html
        auth_response.raise_for_status = MagicMock()

        mock_auth_client = AsyncMock()
        mock_auth_client.get = AsyncMock(return_value=auth_response)
        mock_auth_client.__aenter__ = AsyncMock(return_value=mock_auth_client)
        mock_auth_client.__aexit__ = AsyncMock(return_value=False)

        # Second httpx.AsyncClient: calls /films and /showtimes endpoints
        async def api_get(url: str, **kwargs: object) -> MagicMock:
            r = MagicMock()
            r.status_code = 200
            if "/films" in url:
                r.json = MagicMock(return_value=films_data)
            else:
                r.json = MagicMock(return_value=showtimes_data)
            return r

        mock_api_client = AsyncMock()
        mock_api_client.get = api_get
        mock_api_client.__aenter__ = AsyncMock(return_value=mock_api_client)
        mock_api_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", side_effect=[mock_auth_client, mock_api_client]):
            showings = await scraper.get_showings(date(2026, 2, 20), date(2026, 2, 20))

        # showtimes.json has 3 entries: FILM001, FILM002, UNKNOWN_FILM (fallback)
        assert len(showings) == 3
        titles = {s.title for s in showings}
        assert "The Grand Budapest Hotel" in titles
        assert "Nosferatu" in titles
        assert all(s.start_time.tzinfo is not None for s in showings)

    async def test_returns_empty_list_when_auth_token_not_found(
        self, scraper: CurzonScraper
    ) -> None:
        auth_response = MagicMock()
        auth_response.text = "<html>No token here</html>"
        auth_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=auth_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 2, 20), date(2026, 2, 20))

        assert showings == []
