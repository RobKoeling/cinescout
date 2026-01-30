"""The Garden Cinema scraper."""

import logging
import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")


class GardenScraper(BaseScraper):
    """
    Scraper for The Garden Cinema.

    Uses Savoy Systems ticketing platform.
    """

    BASE_URL = "https://www.thegardencinema.co.uk"

    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch showings from The Garden Cinema."""
        showings: list[RawShowing] = []

        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout) as client:
                # Fetch main page
                response = await client.get(self.BASE_URL)
                response.raise_for_status()

                showings = self._parse_html(response.text, date_from, date_to)

        except Exception as e:
            logger.error(f"Garden Cinema scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Garden Cinema: Found {len(showings)} showings")
        return showings

    def _parse_html(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        """Parse Garden Cinema HTML to extract showings."""
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        # Find all links that are booking links (point to bookings subdomain)
        booking_links = soup.find_all("a", href=re.compile(r"bookings\.thegardencinema\.co\.uk"))

        # Group by film - look for film title links
        film_links = soup.find_all("a", href=re.compile(r"/film/[^/]+/$"))

        # Build a mapping of films and their associated showing times
        for film_link in film_links:
            try:
                # Extract film title and clean it
                film_text = film_link.get_text(strip=True)
                # Remove rating suffix (e.g., "Film Title 12A" -> "Film Title")
                title = re.sub(r'\s+(U|PG|12A?|15|18)$', '', film_text)
                title = self.normalise_title(title)

                if not title or len(title) < 2:
                    continue

                # Find parent container to get associated showtimes
                parent = film_link.find_parent()
                if not parent:
                    continue

                # Look for sibling or nearby booking links
                container = parent.find_parent()
                if not container:
                    container = parent

                # Find time links near this film
                time_links = container.find_all("a", href=re.compile(r"bookings\.thegardencinema\.co\.uk"))

                for time_link in time_links:
                    try:
                        time_text = time_link.get_text(strip=True)
                        booking_url = time_link.get("href")

                        # Try to extract time from link text
                        # Common patterns: "15:30", "3:30 pm", "Fri 30 Jan"
                        time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', time_text)
                        if not time_match:
                            continue

                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))

                        # Try to extract date from nearby text
                        # Look for date patterns in the link text or nearby elements
                        date_match = re.search(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
                                             time_text, re.IGNORECASE)

                        showing_date = date_from  # Default to date_from
                        if date_match:
                            day = int(date_match.group(1))
                            month_str = date_match.group(2)
                            month_map = {
                                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                            }
                            month = month_map.get(month_str.lower(), date_from.month)
                            year = date_from.year
                            showing_date = date(year, month, day)

                        # Check if date is in range
                        if not (date_from <= showing_date <= date_to):
                            continue

                        start_time = datetime(
                            showing_date.year,
                            showing_date.month,
                            showing_date.day,
                            hour,
                            minute,
                            tzinfo=LONDON_TZ,
                        )

                        showing = RawShowing(
                            title=title,
                            start_time=start_time,
                            booking_url=booking_url if booking_url else None,
                        )
                        showings.append(showing)
                        logger.debug(f"Parsed: {title} at {start_time}")

                    except Exception as e:
                        logger.warning(f"Failed to parse time link: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to parse film: {e}")
                continue

        return showings
