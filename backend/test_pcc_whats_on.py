"""Test Prince Charles scraper with /whats-on/ page."""

import asyncio
import logging
from datetime import date

from cinescout.scrapers.prince_charles import PrinceCharlesScraper

logging.basicConfig(level=logging.DEBUG)


async def test():
    scraper = PrinceCharlesScraper()

    # Read the saved HTML
    with open("prince_charles_whats_on.html", "r") as f:
        html = f.read()

    # Test with date range
    showings = scraper._parse_html(html, date(2026, 1, 30), date(2026, 2, 5))

    print(f"\nFound {len(showings)} showings")

    # Group by film
    by_film = {}
    for showing in showings:
        if showing.title not in by_film:
            by_film[showing.title] = []
        by_film[showing.title].append(showing)

    print(f"Films: {len(by_film)}\n")

    for title, film_showings in list(by_film.items())[:5]:
        print(f"{title}: {len(film_showings)} showings")
        for showing in film_showings[:3]:
            print(f"  - {showing.start_time}")


if __name__ == "__main__":
    asyncio.run(test())
