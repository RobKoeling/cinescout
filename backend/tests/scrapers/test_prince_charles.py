"""Unit tests for the Prince Charles Cinema scraper."""

from datetime import date
from pathlib import Path

import pytest

from cinescout.scrapers.prince_charles import PrinceCharlesScraper

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prince_charles"


@pytest.fixture
def scraper() -> PrinceCharlesScraper:
    return PrinceCharlesScraper()


@pytest.fixture
def whats_on_html() -> str:
    return (FIXTURE_DIR / "whats_on.html").read_text()


class TestPrinceCharlesParseHtml:
    def test_extracts_showings(self, scraper: PrinceCharlesScraper, whats_on_html: str) -> None:
        showings = scraper._parse_html(whats_on_html, date(2026, 1, 1), date(2027, 12, 31))
        assert len(showings) > 0

    def test_year_extracted_from_running_time(
        self, scraper: PrinceCharlesScraper, whats_on_html: str
    ) -> None:
        showings = scraper._parse_html(whats_on_html, date(2026, 1, 1), date(2027, 12, 31))
        years = {s.year for s in showings}
        assert 1997 in years  # Cure (1997)
        assert 1989 in years  # The Killer (1989)

    def test_year_used_for_disambiguation(
        self, scraper: PrinceCharlesScraper, whats_on_html: str
    ) -> None:
        # The Killer (1989) should carry year=1989, not be confused with other
        # films of the same name from different years.
        showings = scraper._parse_html(whats_on_html, date(2026, 1, 1), date(2027, 12, 31))
        killer_showings = [s for s in showings if "Killer" in s.title]
        assert killer_showings, "Expected at least one The Killer showing"
        assert all(s.year == 1989 for s in killer_showings)

    def test_all_showings_have_year(
        self, scraper: PrinceCharlesScraper, whats_on_html: str
    ) -> None:
        showings = scraper._parse_html(whats_on_html, date(2026, 1, 1), date(2027, 12, 31))
        missing_year = [s.title for s in showings if s.year is None]
        assert not missing_year, f"Showings missing year: {missing_year}"

    def test_start_times_are_timezone_aware(
        self, scraper: PrinceCharlesScraper, whats_on_html: str
    ) -> None:
        showings = scraper._parse_html(whats_on_html, date(2026, 1, 1), date(2027, 12, 31))
        assert all(s.start_time.tzinfo is not None for s in showings)
