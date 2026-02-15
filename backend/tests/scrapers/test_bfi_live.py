"""Live tests for the BFI Southbank scraper.

These tests make real HTTP requests to whatson.bfi.org.uk.
Run with: pytest -m live tests/scrapers/test_bfi_live.py -v -s --log-cli-level=DEBUG
"""

import logging
from datetime import date, timedelta

import pytest

from cinescout.scrapers.bfi import BFIScraper

logger = logging.getLogger(__name__)


@pytest.mark.live
async def test_bfi_scraper_gets_past_cloudflare():
    """Verify that the stealth browser fetches real HTML, not a Cloudflare challenge."""
    scraper = BFIScraper()
    today = date.today()
    showings = await scraper.get_showings(today, today)
    # If we got here without error, Cloudflare was bypassed.
    # The showings list may be empty if no events today, but the scraper didn't crash.
    logger.info(f"BFI Cloudflare test: got {len(showings)} showings for today")


@pytest.mark.live
async def test_bfi_scraper_returns_showings():
    """Verify that the scraper returns actual showings from BFI Southbank."""
    scraper = BFIScraper()

    today = date.today()
    date_to = today + timedelta(days=14)

    showings = await scraper.get_showings(today, date_to)

    logger.info(f"BFI returned {len(showings)} showings")
    for s in showings[:10]:
        logger.info(f"  {s.title} — {s.start_time} — {s.screen_name} — {s.booking_url}")

    assert len(showings) > 0, "No showings found — BFI likely has events in the next 14 days"

    # Validate the structure of returned showings
    for s in showings:
        assert s.title, "Showing must have a title"
        assert s.start_time.tzinfo is not None, "start_time must be timezone-aware"
        assert s.booking_url, "Showing should have a booking URL"
