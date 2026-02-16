"""Unit tests for The Nickel Cinema scraper."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from cinescout.scrapers.nickel import NickelScraper

LONDON_TZ = ZoneInfo("Europe/London")
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "nickel"

DATE_FROM = date(2026, 2, 17)
DATE_TO = date(2026, 3, 2)


@pytest.fixture
def scraper() -> NickelScraper:
    return NickelScraper()


@pytest.fixture
def fixture_html() -> str:
    return (FIXTURE_DIR / "homepage.html").read_text()


# ---------------------------------------------------------------------------
# _parse_html — pure parsing, no HTTP
# ---------------------------------------------------------------------------


class TestNickelParseHtml:
    def test_extracts_showings_in_date_range(
        self, scraper: NickelScraper, fixture_html: str
    ) -> None:
        # 101 (Feb 22), 102 (Feb 24), 103 (Feb 22) — 100 (Feb 1) excluded
        showings = scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        assert len(showings) == 3

    def test_excludes_showings_outside_date_range(
        self, scraper: NickelScraper, fixture_html: str
    ) -> None:
        showings = scraper._parse_html(fixture_html, date(2026, 2, 24), date(2026, 2, 24))
        assert len(showings) == 1
        assert showings[0].title == "POINT BLANK"

    def test_returns_empty_list_for_no_screening_cards(self, scraper: NickelScraper) -> None:
        showings = scraper._parse_html("<html><body><p>No screenings</p></body></html>",
                                       DATE_FROM, DATE_TO)
        assert showings == []

    def test_includes_sold_out_showings(
        self, scraper: NickelScraper, fixture_html: str
    ) -> None:
        showings = scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        titles = {s.title for s in showings}
        assert "POINT BLANK" in titles


# ---------------------------------------------------------------------------
# _parse_card — pure parsing, no HTTP
# ---------------------------------------------------------------------------


class TestNickelParseCard:
    def setup_method(self) -> None:
        self.scraper = NickelScraper()

    def test_parses_title(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        titles = {s.title for s in showings}
        assert "THE PARALLAX VIEW" in titles
        assert "BLOOD SIMPLE" in titles

    def test_builds_booking_url(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        urls = {s.booking_url for s in showings}
        assert "https://thenickel.co.uk/screening/101" in urls
        assert "https://thenickel.co.uk/screening/102" in urls

    def test_parses_time_with_minutes(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        parallax = next(s for s in showings if s.title == "THE PARALLAX VIEW")
        assert parallax.start_time == datetime(2026, 2, 22, 18, 30, tzinfo=LONDON_TZ)

    def test_parses_time_without_minutes(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        point_blank = next(s for s in showings if s.title == "POINT BLANK")
        assert point_blank.start_time == datetime(2026, 2, 24, 20, 0, tzinfo=LONDON_TZ)

    def test_parses_digital_format_tag(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        parallax = next(s for s in showings if s.title == "THE PARALLAX VIEW")
        assert parallax.format_tags == "Digital"

    def test_parses_vhs_format_tag(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        blood_simple = next(s for s in showings if s.title == "BLOOD SIMPLE")
        assert blood_simple.format_tags == "VHS"

    def test_start_time_is_timezone_aware(self, fixture_html: str) -> None:
        showings = self.scraper._parse_html(fixture_html, DATE_FROM, DATE_TO)
        assert all(s.start_time.tzinfo is not None for s in showings)


# ---------------------------------------------------------------------------
# _parse_date — pure, no HTTP
# ---------------------------------------------------------------------------


class TestNickelParseDate:
    def setup_method(self) -> None:
        self.scraper = NickelScraper()
        self.ref = date(2026, 2, 17)

    def test_parses_standard_date(self) -> None:
        assert self.scraper._parse_date("Sunday 22.2", self.ref) == date(2026, 2, 22)

    def test_parses_single_digit_day(self) -> None:
        assert self.scraper._parse_date("Sunday 1.2", self.ref) == date(2026, 2, 1)

    def test_returns_none_for_missing_pattern(self) -> None:
        assert self.scraper._parse_date("No date here", self.ref) is None

    def test_rolls_forward_for_year_boundary(self) -> None:
        # Dec showing viewed in Jan: 1.12 is >30 days before 2027-01-15
        ref_jan = date(2027, 1, 15)
        result = self.scraper._parse_date("Monday 1.12", ref_jan)
        assert result == date(2027, 12, 1)

    def test_does_not_roll_forward_within_30_days(self) -> None:
        # Feb 1 is 16 days before Feb 17 — stays in same year
        result = self.scraper._parse_date("Sunday 1.2", self.ref)
        assert result == date(2026, 2, 1)


# ---------------------------------------------------------------------------
# _parse_time — pure, no HTTP
# ---------------------------------------------------------------------------


class TestNickelParseTime:
    def setup_method(self) -> None:
        self.scraper = NickelScraper()

    def test_parses_time_with_minutes(self) -> None:
        assert self.scraper._parse_time("6:30pm") == (18, 30)

    def test_parses_time_without_minutes(self) -> None:
        assert self.scraper._parse_time("8pm") == (20, 0)

    def test_parses_am_time(self) -> None:
        assert self.scraper._parse_time("11:30am") == (11, 30)

    def test_parses_12pm_as_noon(self) -> None:
        assert self.scraper._parse_time("12pm") == (12, 0)

    def test_parses_12am_as_midnight(self) -> None:
        assert self.scraper._parse_time("12am") == (0, 0)

    def test_returns_none_for_invalid_string(self) -> None:
        assert self.scraper._parse_time("no time here") is None

    def test_handles_whitespace(self) -> None:
        assert self.scraper._parse_time("  9pm  ") == (21, 0)


# ---------------------------------------------------------------------------
# get_showings — mocked HTTP
# ---------------------------------------------------------------------------


class TestNickelGetShowings:
    async def test_returns_showings_from_mocked_response(self, fixture_html: str) -> None:
        scraper = NickelScraper()

        mock_response = MagicMock()
        mock_response.text = fixture_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(DATE_FROM, DATE_TO)

        assert len(showings) == 3
        assert all(s.start_time.tzinfo is not None for s in showings)

    async def test_returns_empty_list_on_http_error(self) -> None:
        scraper = NickelScraper()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            showings = await scraper.get_showings(DATE_FROM, DATE_TO)

        assert showings == []
