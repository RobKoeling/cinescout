"""Create test data for development/testing."""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from cinescout.database import AsyncSessionLocal
from cinescout.models import Cinema, Film, Showing

LONDON_TZ = ZoneInfo("Europe/London")


async def create_test_data():
    """Create test films and showings."""
    async with AsyncSessionLocal() as db:
        # Create test films
        films_data = [
            {
                "id": "the-godfather-1972",
                "title": "The Godfather",
                "year": 1972,
                "directors": ["Francis Ford Coppola"],
                "countries": ["US"],
                "runtime": 175,
                "overview": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.",
            },
            {
                "id": "parasite-2019",
                "title": "Parasite",
                "year": 2019,
                "directors": ["Bong Joon-ho"],
                "countries": ["KR"],
                "runtime": 132,
                "overview": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
            },
            {
                "id": "la-haine-1995",
                "title": "La Haine",
                "year": 1995,
                "directors": ["Mathieu Kassovitz"],
                "countries": ["FR"],
                "runtime": 98,
                "overview": "24 hours in the lives of three young men in the French suburbs the day after a violent riot.",
            },
        ]

        for film_data in films_data:
            film = Film(**film_data)
            db.add(film)

        # Get cinemas
        bfi = await db.get(Cinema, "bfi-southbank")
        curzon = await db.get(Cinema, "curzon-soho")

        # Create showings for next 3 days
        base_date = datetime.now(LONDON_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

        showings_data = [
            # Today - The Godfather at BFI
            {
                "cinema_id": bfi.id,
                "film_id": "the-godfather-1972",
                "start_time": base_date.replace(hour=18, minute=30),
                "screen_name": "NFT1",
                "price": 12.50,
                "booking_url": "https://whatson.bfi.org.uk/book",
            },
            {
                "cinema_id": bfi.id,
                "film_id": "the-godfather-1972",
                "start_time": base_date.replace(hour=21, minute=15),
                "screen_name": "NFT2",
                "price": 12.50,
                "booking_url": "https://whatson.bfi.org.uk/book",
            },
            # Today - Parasite at Curzon
            {
                "cinema_id": curzon.id,
                "film_id": "parasite-2019",
                "start_time": base_date.replace(hour=19, minute=0),
                "price": 15.00,
                "booking_url": "https://www.curzoncinemas.com/book",
            },
            # Tomorrow - La Haine at BFI
            {
                "cinema_id": bfi.id,
                "film_id": "la-haine-1995",
                "start_time": (base_date + timedelta(days=1)).replace(hour=20, minute=30),
                "screen_name": "NFT1",
                "format_tags": "35mm",
                "price": 12.50,
                "booking_url": "https://whatson.bfi.org.uk/book",
            },
            # Tomorrow - Parasite at BFI
            {
                "cinema_id": bfi.id,
                "film_id": "parasite-2019",
                "start_time": (base_date + timedelta(days=1)).replace(hour=18, minute=0),
                "screen_name": "NFT3",
                "price": 12.50,
                "booking_url": "https://whatson.bfi.org.uk/book",
            },
            # Tomorrow - Parasite at Curzon
            {
                "cinema_id": curzon.id,
                "film_id": "parasite-2019",
                "start_time": (base_date + timedelta(days=1)).replace(hour=21, minute=0),
                "price": 15.00,
                "booking_url": "https://www.curzoncinemas.com/book",
            },
        ]

        for showing_data in showings_data:
            showing = Showing(**showing_data)
            db.add(showing)

        await db.commit()
        print("✓ Test data created successfully")
        print(f"  - {len(films_data)} films")
        print(f"  - {len(showings_data)} showings")


if __name__ == "__main__":
    asyncio.run(create_test_data())
