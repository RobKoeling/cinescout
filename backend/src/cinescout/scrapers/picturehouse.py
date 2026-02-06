"""Picturehouse Cinemas scraper using their API."""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

# Mapping of cinema slugs to API IDs
CINEMA_ID_MAP = {
    "picturehouse-central": "010",
    "greenwich-picturehouse": "011",
    "hackney-picturehouse": "019",
    "the-gate": "014",
    "the-ritzy": "008",
    "clapham-picturehouse": "007",
    "crouch-end-picturehouse": "009",
    "east-dulwich": "013",
    "finsbury-park": "020",
    "ealing-picturehouse": "016",
    "west-norwood-picturehouse": "024",
}


class PicturehouseScraper(BaseScraper):
    """
    Scraper for Picturehouse Cinemas.

    Uses the Picturehouse API to fetch showtimes.
    """

    BASE_URL = "https://www.picturehouses.com"
    API_URL = "https://www.picturehouses.com/api/scheduled-movies-ajax"

    def __init__(self, cinema_slug: str = "picturehouse-central"):
        """
        Initialize scraper for a specific Picturehouse cinema.

        Args:
            cinema_slug: The cinema slug (e.g., "picturehouse-central")
        """
        self.cinema_slug = cinema_slug
        self.cinema_id = CINEMA_ID_MAP.get(cinema_slug)
        
        if not self.cinema_id:
            logger.warning(f"Unknown cinema slug: {cinema_slug}, will fetch all cinemas")

    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch showings from Picturehouse API."""
        showings: list[RawShowing] = []

        try:
            # Fetch data for each date in range
            current_date = date_from
            while current_date <= date_to:
                date_showings = await self._fetch_date(current_date)
                showings.extend(date_showings)
                current_date = current_date + timedelta(days=1)

        except Exception as e:
            logger.error(f"Picturehouse scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Picturehouse ({self.cinema_slug}): Found {len(showings)} showings")
        return showings

    async def _fetch_date(self, showing_date: date) -> list[RawShowing]:
        """Fetch showings for a specific date."""
        showings: list[RawShowing] = []

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': f'{self.BASE_URL}/whats-on',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'cinema_id': self.cinema_id or '',
            'date': showing_date.strftime('%Y-%m-%d'),
        }

        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
                response = await client.post(self.API_URL, headers=headers, data=data)
                response.raise_for_status()

                result = response.json()

                if result.get('response') != 'success':
                    logger.warning(f"API returned error: {result.get('message', 'Unknown error')}")
                    return []

                movies = result.get('movies', [])
                logger.debug(f"Found {len(movies)} movies for {showing_date}")

                for movie in movies:
                    try:
                        showings.extend(self._parse_movie(movie))
                    except Exception as e:
                        logger.warning(f"Failed to parse movie: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to fetch Picturehouse data for {showing_date}: {e}")
            return []

        return showings

    def _parse_movie(self, movie: dict) -> list[RawShowing]:
        """Parse a movie dict from the API into RawShowing objects."""
        showings: list[RawShowing] = []

        title_raw = movie.get('Title', '')
        if not title_raw:
            return []

        title = self.normalise_title(title_raw)
        if not title or len(title) < 2:
            return []

        # Extract showtimes
        show_times = movie.get('show_times', [])
        if not show_times:
            return []

        for show_time in show_times:
            try:
                # Skip if this showing is for a different cinema
                if self.cinema_id and show_time.get('CinemaId') != self.cinema_id:
                    continue

                # Parse showtime (ISO format: "2026-03-25T20:00:00")
                showtime_str = show_time.get('Showtime')
                if not showtime_str:
                    continue

                # Parse ISO datetime
                start_time = datetime.fromisoformat(showtime_str)
                
                # Ensure timezone is set
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=LONDON_TZ)

                # Build booking URL from EventId
                event_id = show_time.get('EventId')
                booking_url = None
                if event_id:
                    booking_url = f"{self.BASE_URL}/booking/{event_id}"

                showing = RawShowing(
                    title=title,
                    start_time=start_time,
                    booking_url=booking_url,
                )
                showings.append(showing)
                logger.debug(f"Parsed: {title} at {start_time}")

            except Exception as e:
                logger.warning(f"Failed to parse showtime: {e}")
                continue

        return showings
