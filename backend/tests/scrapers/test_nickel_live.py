"""Live tests for The Nickel Cinema scraper.

These tests make real HTTP requests to thenickel.co.uk.
Run with: pytest -m live tests/scrapers/test_nickel_live.py -v -s --log-cli-level=DEBUG
"""

import logging
from datetime import date, timedelta

import pytest

from cinescout.scrapers.nickel import NickelScraper

logger = logging.getLogger(__name__)


@pytest.mark.live
async def test_nickel_scraper_returns_showings():
    """Verify the scraper returns actual showings from The Nickel homepage."""
    scraper = NickelScraper()

    today = date.today()
    date_to = today + timedelta(days=14)

    showings = await scraper.get_showings(today, date_to)

    logger.info(f"The Nickel returned {len(showings)} showings")
    for s in showings[:10]:
        logger.info(f"  {s.title} — {s.start_time} — {s.format_tags} — {s.booking_url}")

    assert len(showings) > 0, "No showings found — The Nickel should have events in the next 14 days"

    for s in showings:
        assert s.title, "Showing must have a title"
        assert s.start_time.tzinfo is not None, "start_time must be timezone-aware"
        assert s.booking_url and s.booking_url.startswith("https://thenickel.co.uk/screening/"), (
            f"Expected booking URL starting with https://thenickel.co.uk/screening/, got {s.booking_url!r}"
        )


@pytest.mark.live
async def test_nickel_scraper_parses_format_tags():
    """Verify that at least some showings have format tags (Digital or VHS)."""
    scraper = NickelScraper()

    today = date.today()
    date_to = today + timedelta(days=14)

    showings = await scraper.get_showings(today, date_to)

    tagged = [s for s in showings if s.format_tags]
    logger.info(f"The Nickel: {len(tagged)}/{len(showings)} showings have format tags")
    for s in tagged:
        logger.info(f"  {s.title} — {s.format_tags}")

    assert len(tagged) > 0, "Expected at least some showings to have a format tag (Digital/VHS)"
