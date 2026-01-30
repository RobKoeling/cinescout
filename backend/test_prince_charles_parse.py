"""Quick test of Prince Charles scraper parsing with debug output."""

import asyncio
import logging
from datetime import date

from cinescout.scrapers.prince_charles import PrinceCharlesScraper

logging.basicConfig(level=logging.DEBUG)


async def test():
    scraper = PrinceCharlesScraper()

    # Read the saved HTML
    with open("prince_charles_page.html", "r") as f:
        html = f.read()

    # Test with actual dates (today's date for homepage)
    showings = scraper._parse_html(html, date(2026, 1, 30), date(2026, 2, 5))

    print(f"\nFound {len(showings)} showings")
    for showing in showings[:10]:
        print(f"  - {showing.title} at {showing.start_time}")
        if showing.booking_url:
            print(f"    Booking: {showing.booking_url[:80]}")


if __name__ == "__main__":
    asyncio.run(test())
