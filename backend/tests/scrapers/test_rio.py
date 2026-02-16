"""Unit tests for the Rio Cinema scraper."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cinescout.scrapers.rio import RioScraper

LONDON_TZ = ZoneInfo("Europe/London")
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rio"


@pytest.fixture
def scraper() -> RioScraper:
    return RioScraper()


@pytest.fixture
def fixture_html() -> str:
    return (FIXTURE_DIR / "whats_on.html").read_text()


# ---------------------------------------------------------------------------
# _parse_html — pure parsing, no HTTP
# ---------------------------------------------------------------------------


class TestRioParseHtml:
    def test_extracts_showings_in_date_range(self, scraper: RioScraper, fixture_html: str) -> None:
        # Nosferatu: Feb 20 + Feb 21 = 2; The Substance: Feb 20 = 1; Old Film excluded
        showings = scraper._parse_html(fixture_html, date(2026, 2, 20), date(2026, 2, 21))
        assert len(showings) == 3

    def test_excludes_showings_outside_date_range(
        self, scraper: RioScraper, fixture_html: str
    ) -> None:
        showings = scraper._parse_html(fixture_html, date(2026, 2, 20), date(2026, 2, 20))
        # Only Feb 20: Nosferatu + The Substance = 2
        assert len(showings) == 2

    def test_returns_empty_list_when_var_events_missing(self, scraper: RioScraper) -> None:
        showings = scraper._parse_html(
            "<html><body>No events here</body></html>", date(2026, 2, 20), date(2026, 2, 21)
        )
        assert showings == []

    def test_normalises_title_removing_preview_prefix_and_year(
        self, scraper: RioScraper, fixture_html: str
    ) -> None:
        # "Preview: The Substance (2024)" → "The Substance"
        showings = scraper._parse_html(fixture_html, date(2026, 2, 20), date(2026, 2, 20))
        titles = {s.title for s in showings}
        assert "The Substance" in titles
        assert not any("Preview:" in t for t in titles)
        assert not any("(2024)" in t for t in titles)

    def test_handles_json_with_semicolons_in_strings(self, scraper: RioScraper) -> None:
        # raw_decode must handle subsequent `};` patterns that look like end-of-assignment
        html = 'var Events = {"Events":[]}; var X = {"k": "v; with }; inside"};'
        showings = scraper._parse_html(html, date(2026, 2, 20), date(2026, 2, 21))
        assert showings == []  # no events, but no crash


# ---------------------------------------------------------------------------
# _parse_performance — pure parsing, no HTTP
# ---------------------------------------------------------------------------


class TestRioParsePerformance:
    def setup_method(self) -> None:
        self.scraper = RioScraper()
        self.date_from = date(2026, 2, 20)
        self.date_to = date(2026, 2, 21)

    def test_parses_basic_performance(self) -> None:
        perf = {
            "StartDate": "2026-02-20",
            "StartTime": "1830",
            "URL": "Booking?ShowtimeId=1001",
            "AuditoriumName": "Screen 1",
        }
        showing = self.scraper._parse_performance("Nosferatu", perf, self.date_from, self.date_to)
        assert showing is not None
        assert showing.title == "Nosferatu"
        assert showing.start_time == datetime(2026, 2, 20, 18, 30, tzinfo=LONDON_TZ)
        assert showing.screen_name == "Screen 1"

    def test_start_time_is_timezone_aware(self) -> None:
        perf = {"StartDate": "2026-02-20", "StartTime": "1900", "URL": "Booking?id=1"}
        showing = self.scraper._parse_performance("Film", perf, self.date_from, self.date_to)
        assert showing is not None
        assert showing.start_time.tzinfo is not None

    def test_parses_time_with_leading_zero(self) -> None:
        perf = {"StartDate": "2026-02-20", "StartTime": "0930", "URL": "Booking?id=1"}
        showing = self.scraper._parse_performance("Film", perf, self.date_from, self.date_to)
        assert showing is not None
        assert showing.start_time.hour == 9
        assert showing.start_time.minute == 30

    def test_returns_none_when_performance_outside_date_range(self) -> None:
        perf = {"StartDate": "2026-02-15", "StartTime": "1800", "URL": "Booking?id=99"}
        showing = self.scraper._parse_performance("Old Film", perf, self.date_from, self.date_to)
        assert showing is None

    def test_returns_none_when_start_date_missing(self) -> None:
        perf = {"StartTime": "1800", "URL": "Booking?id=1"}
        showing = self.scraper._parse_performance("Film", perf, self.date_from, self.date_to)
        assert showing is None

    def test_returns_none_when_start_time_missing(self) -> None:
        perf = {"StartDate": "2026-02-20", "URL": "Booking?id=1"}
        showing = self.scraper._parse_performance("Film", perf, self.date_from, self.date_to)
        assert showing is None

    def test_builds_relative_booking_url(self) -> None:
        perf = {
            "StartDate": "2026-02-20",
            "StartTime": "1800",
            "URL": "Booking?ShowtimeId=1001",
        }
        showing = self.scraper._parse_performance("Film", perf, self.date_from, self.date_to)
        assert showing is not None
        assert showing.booking_url == "https://riocinema.org.uk/Rio.dll/Booking?ShowtimeId=1001"

    def test_passes_through_absolute_booking_url(self) -> None:
        perf = {
            "StartDate": "2026-02-20",
            "StartTime": "1800",
            "URL": "https://external.example.com/book",
        }
        showing = self.scraper._parse_performance("Film", perf, self.date_from, self.date_to)
        assert showing is not None
        assert showing.booking_url == "https://external.example.com/book"


# ---------------------------------------------------------------------------
# _extract_format_tags — pure, no HTTP
# ---------------------------------------------------------------------------


class TestRioExtractFormatTags:
    def setup_method(self) -> None:
        self.scraper = RioScraper()

    def test_returns_none_when_no_flags_active(self) -> None:
        assert self.scraper._extract_format_tags({"HoH": "N", "RS": "N", "QA": "N"}) is None

    def test_returns_none_for_empty_perf(self) -> None:
        assert self.scraper._extract_format_tags({}) is None

    def test_returns_single_tag(self) -> None:
        assert self.scraper._extract_format_tags({"QA": "Y"}) == "Q&A"

    def test_returns_multiple_tags_comma_separated(self) -> None:
        result = self.scraper._extract_format_tags({"HoH": "Y", "RS": "Y"})
        assert result is not None
        assert "Hard of Hearing" in result
        assert "Relaxed Screening" in result

    def test_ignores_flags_set_to_n(self) -> None:
        result = self.scraper._extract_format_tags({"QA": "N", "HoH": "Y"})
        assert result is not None
        assert "Q&A" not in result
        assert "Hard of Hearing" in result


# ---------------------------------------------------------------------------
# get_showings — mocked HTTP
# ---------------------------------------------------------------------------


class TestRioGetShowings:
    async def test_returns_showings_from_mocked_response(self, fixture_html: str) -> None:
        scraper = RioScraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = fixture_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 2, 20), date(2026, 2, 21))

        assert len(showings) == 3
        titles = {s.title for s in showings}
        assert "Nosferatu" in titles
        assert "The Substance" in titles
        assert all(s.start_time.tzinfo is not None for s in showings)

    async def test_returns_empty_list_on_http_error(self) -> None:
        scraper = RioScraper()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(date(2026, 2, 20), date(2026, 2, 21))

        assert showings == []
