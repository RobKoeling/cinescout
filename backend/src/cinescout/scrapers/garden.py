"""The Garden Cinema scraper."""

import logging
import re
from datetime import date, datetime
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

    Uses Savoy Systems ticketing platform with structured film listings.
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
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
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

        # Find all film containers
        film_containers = soup.find_all("div", class_="films-list__by-date__film")

        logger.debug(f"Found {len(film_containers)} film containers")

        for container in film_containers:
            try:
                # Extract film title from the h1 element
                title_elem = container.find("h1", class_="films-list__by-date__film__title")
                if not title_elem:
                    continue

                # Get the title text (the link text inside h1, excluding the rating span)
                title_link = title_elem.find("a")
                if not title_link:
                    continue

                # Remove rating span before getting text
                rating_span = title_link.find("span", class_="films-list__by-date__film__rating")
                if rating_span:
                    rating_span.decompose()

                title_text = title_link.get_text(strip=True)
                title = self.normalise_title(title_text)

                if not title or len(title) < 2:
                    continue

                logger.debug(f"Processing film: {title}")

                # Find the screening times container
                screening_times = container.find("div", class_="films-list__by-date__film__screeningtimes")
                if not screening_times:
                    continue

                # Find all screening panels
                screening_panels = screening_times.find_all("div", class_="screening-panel")

                for panel in screening_panels:
                    try:
                        # Extract date from the date title
                        date_elem = panel.find("div", class_="screening-panel__date-title")
                        if not date_elem:
                            continue

                        date_text = date_elem.get_text(strip=True)
                        # Parse date like "Fri 30 Jan" or "Sat 31 Jan"
                        date_match = re.search(r'\b(\d{1,2})\s+(\w+)\b', date_text)
                        if not date_match:
                            continue

                        day = int(date_match.group(1))
                        month_str = date_match.group(2)
                        month_map = {
                            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                        }
                        month = month_map.get(month_str.lower())
                        if not month:
                            continue

                        year = date_from.year
                        showing_date = date(year, month, day)

                        # Check if date is in range
                        if not (date_from <= showing_date <= date_to):
                            continue

                        # Find all time links in this panel
                        time_links = panel.find_all("a", href=re.compile(r"bookings\.thegardencinema\.co\.uk"))

                        for time_link in time_links:
                            try:
                                time_text = time_link.get_text(strip=True)
                                booking_url = time_link.get("href")

                                # Parse time (format: "17:30")
                                time_match = re.match(r'^(\d{1,2}):(\d{2})$', time_text)
                                if not time_match:
                                    continue

                                hour = int(time_match.group(1))
                                minute = int(time_match.group(2))

                                start_time = datetime(
                                    showing_date.year,
                                    showing_date.month,
                                    showing_date.day,
                                    hour,
                                    minute,
                                    tzinfo=LONDON_TZ,
                                )

                                # Extract screen name if available
                                screen_elem = panel.find("div", class_="screening-panel__day")
                                screen_name = screen_elem.get_text(strip=True) if screen_elem else None

                                showing = RawShowing(
                                    title=title,
                                    start_time=start_time,
                                    booking_url=booking_url,
                                    screen_name=screen_name,
                                )
                                showings.append(showing)
                                logger.debug(f"Added: {title} at {start_time}")

                            except Exception as e:
                                logger.warning(f"Failed to parse time link '{time_text}': {e}")
                                continue

                    except Exception as e:
                        logger.warning(f"Failed to parse screening panel: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to parse film container: {e}")
                continue

        return showings
