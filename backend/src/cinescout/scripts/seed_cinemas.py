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
        {
            "id": "greenwich-picturehouse",
            "name": "Greenwich Picturehouse",
            "city": "london",
            "address": "180 Greenwich High Road",
            "postcode": "SE10 8NN",
            "latitude": 51.4769,
            "longitude": -0.0100,
            "website": "https://www.picturehouses.com/cinema/greenwich-picturehouse",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "greenwich-picturehouse"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "hackney-picturehouse",
            "name": "Hackney Picturehouse",
            "city": "london",
            "address": "270 Mare Street",
            "postcode": "E8 1HE",
            "latitude": 51.5455,
            "longitude": -0.0553,
            "website": "https://www.picturehouses.com/cinema/hackney-picturehouse",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "hackney-picturehouse"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "the-gate-picturehouse",
            "name": "The Gate Picturehouse",
            "city": "london",
            "address": "87 Notting Hill Gate",
            "postcode": "W11 3JZ",
            "latitude": 51.5092,
            "longitude": -0.1967,
            "website": "https://www.picturehouses.com/cinema/the-gate",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "the-gate"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "the-ritzy-picturehouse",
            "name": "The Ritzy Picturehouse",
            "city": "london",
            "address": "Brixton Oval, Coldharbour Lane",
            "postcode": "SW2 1JG",
            "latitude": 51.4617,
            "longitude": -0.1149,
            "website": "https://www.picturehouses.com/cinema/the-ritzy",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "the-ritzy"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "clapham-picturehouse",
            "name": "Clapham Picturehouse",
            "city": "london",
            "address": "76 Venn Street",
            "postcode": "SW4 0AT",
            "latitude": 51.4621,
            "longitude": -0.1390,
            "website": "https://www.picturehouses.com/cinema/clapham-picturehouse",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "clapham-picturehouse"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "crouch-end-picturehouse",
            "name": "Crouch End Picturehouse",
            "city": "london",
            "address": "165 Tottenham Lane",
            "postcode": "N8 9BT",
            "latitude": 51.5773,
            "longitude": -0.1209,
            "website": "https://www.picturehouses.com/cinema/crouch-end-picturehouse",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "crouch-end-picturehouse"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "east-dulwich-picturehouse",
            "name": "East Dulwich Picturehouse",
            "city": "london",
            "address": "116 Lordship Lane",
            "postcode": "SE22 8HD",
            "latitude": 51.4533,
            "longitude": -0.0742,
            "website": "https://www.picturehouses.com/cinema/east-dulwich",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "east-dulwich"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "finsbury-park-picturehouse",
            "name": "Finsbury Park Picturehouse",
            "city": "london",
            "address": "1 Regal Place, Station Place",
            "postcode": "N4 2DG",
            "latitude": 51.5646,
            "longitude": -0.1065,
            "website": "https://www.picturehouses.com/cinema/finsbury-park",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "finsbury-park"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "ealing-picturehouse",
            "name": "Ealing Picturehouse",
            "city": "london",
            "address": "15 Uxbridge Road",
            "postcode": "W5 5SA",
            "latitude": 51.5142,
            "longitude": -0.3021,
            "website": "https://www.picturehouses.com/cinema/ealing-picturehouse",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "ealing-picturehouse"},
            "has_online_booking": True,
            "supports_availability_check": False,
        },
        {
            "id": "west-norwood-picturehouse",
            "name": "West Norwood Picturehouse",
            "city": "london",
            "address": "2 Knights Hill",
            "postcode": "SE27 0HS",
            "latitude": 51.4319,
            "longitude": -0.1033,
            "website": "https://www.picturehouses.com/cinema/west-norwood-picturehouse",
            "scraper_type": "picturehouse",
            "scraper_config": {"cinema_slug": "west-norwood-picturehouse"},
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
