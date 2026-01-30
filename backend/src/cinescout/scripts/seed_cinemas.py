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
