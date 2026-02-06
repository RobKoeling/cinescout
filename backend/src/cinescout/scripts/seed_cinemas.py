"""Seed script to populate initial cinema data."""

import asyncio

from sqlalchemy import select

from cinescout.database import AsyncSessionLocal
from cinescout.models.cinema import Cinema


async def seed_cinemas() -> None:
    """Seed the database with initial cinema data."""
    cinemas_data = [
        {
            "id": "bfi-southbank",
            "name": "BFI Southbank",
            "city": "london",
            "address": "Belvedere Road, South Bank",
            "postcode": "SE1 8XT",
            "latitude": 51.5065,
            "longitude": -0.1150,
            "website": "https://whatson.bfi.org.uk/Online/default.asp",
            "scraper_type": "bfi",
            "scraper_config": None,
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "curzon-soho",
            "name": "Curzon Soho",
            "city": "london",
            "address": "99 Shaftesbury Avenue",
            "postcode": "W1D 5DY",
            "latitude": 51.5130,
            "longitude": -0.1318,
            "website": "https://www.curzon.com/venues/soho",
            "scraper_type": "curzon",
            "scraper_config": {"venue_id": "2"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "the-garden-cinema",
            "name": "The Garden Cinema",
            "city": "london",
            "address": "42 Exmouth Market",
            "postcode": "EC1R 4QL",
            "latitude": 51.5267,
            "longitude": -0.1090,
            "website": "https://www.thegardencinema.co.uk",
            "scraper_type": "garden",
            "scraper_config": None,
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "prince-charles-cinema",
            "name": "Prince Charles Cinema",
            "city": "london",
            "address": "7 Leicester Place",
            "postcode": "WC2H 7BY",
            "latitude": 51.5112,
            "longitude": -0.1305,
            "website": "https://princecharlescinema.com",
            "scraper_type": "prince-charles",
            "scraper_config": None,
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "picturehouse-central",
            "name": "Picturehouse Central",
            "city": "london",
            "address": "Corner of Shaftesbury Avenue and Great Windmill Street",
            "postcode": "W1D 7DH",
            "latitude": 51.5104,
            "longitude": -0.1338,
            "website": "https://www.picturehouses.com/cinema/picturehouse-central",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "picturehouse-central"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
    ]

    async with AsyncSessionLocal() as session:
        for cinema_data in cinemas_data:
            # Check if cinema already exists
            query = select(Cinema).where(Cinema.id == cinema_data["id"])
            result = await session.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                print(f"Cinema {cinema_data['id']} already exists, skipping")
                continue

            # Create new cinema
            cinema = Cinema(**cinema_data)
            session.add(cinema)
            print(f"Added cinema: {cinema_data['name']}")

        await session.commit()
        print("Cinema seeding complete")


if __name__ == "__main__":
    asyncio.run(seed_cinemas())
