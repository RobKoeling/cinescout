"""Quick test of Garden scraper parsing with debug output."""

import asyncio
import logging
from datetime import date

from cinescout.scrapers.garden import GardenScraper

logging.basicConfig(level=logging.DEBUG)


async def test():
    scraper = GardenScraper()

    # Read the saved HTML
    with open("garden_page.html", "r") as f:
        html = f.read()

    # Test with actual dates
    showings = scraper._parse_html(html, date(2026, 1, 30), date(2026, 2, 5))

    print(f"\nFound {len(showings)} showings")
    for showing in showings[:10]:
        print(f"  - {showing.title} at {showing.start_time}")


if __name__ == "__main__":
    asyncio.run(test())
