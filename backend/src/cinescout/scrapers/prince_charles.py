"""Prince Charles Cinema scraper."""

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


class PrinceCharlesScraper(BaseScraper):
    """
    Scraper for Prince Charles Cinema.

    WordPress-based site with jacro cinema plugin.
    """

    BASE_URL = "https://princecharlescinema.com"

    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch showings from Prince Charles Cinema."""
        showings: list[RawShowing] = []

        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout) as client:
                # Fetch main "What's On" page
                response = await client.get(f"{self.BASE_URL}/whats-on/")
                response.raise_for_status()

                showings = self._parse_html(response.text, date_from, date_to)

        except Exception as e:
            logger.error(f"Prince Charles Cinema scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Prince Charles Cinema: Found {len(showings)} showings")
        return showings

    def _parse_html(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        """Parse Prince Charles Cinema HTML to extract showings."""
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        # Find all film data containers
        film_data_divs = soup.find_all("div", class_="calendarfilm-filmdata")

        logger.debug(f"Found {len(film_data_divs)} film data containers")

        for film_data in film_data_divs:
            try:
                # Extract film title from the link
                film_link = film_data.find("a", href=re.compile(r"/film/"))
                if not film_link:
                    continue

                title_text = film_link.get_text(strip=True)
                title = self.normalise_title(title_text)

                if not title or len(title) < 2:
                    continue

                logger.debug(f"Processing film: {title}")

                # Find the parent container that includes both film data and performance data
                parent_container = film_data.parent
                if not parent_container:
                    continue

                # Find the grandparent (col-md-8) that contains the film and its times
                grandparent = parent_container.parent
                if not grandparent:
                    continue

                # Find all time spans in this film's container
                time_spans = grandparent.find_all("span", class_="time")

                for time_span in time_spans:
                    try:
                        time_text = time_span.get_text(strip=True)

                        # Parse time (format: "5:45 pm" or "18:30")
                        time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
                        if not time_match:
                            continue

                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))

                        # Handle AM/PM if present
                        if "pm" in time_text.lower() and hour != 12:
                            hour += 12
                        elif "am" in time_text.lower() and hour == 12:
                            hour = 0

                        # The homepage shows today's showings
                        # For a full scraper, you'd need to navigate to different dates
                        showing_date = date_from

                        start_time = datetime(
                            showing_date.year,
                            showing_date.month,
                            showing_date.day,
                            hour,
                            minute,
                            tzinfo=LONDON_TZ,
                        )

                        # Check if date is in range
                        if not (date_from <= start_time.date() <= date_to):
                            continue

                        # Try to find booking URL
                        booking_url = None
                        if time_span.parent and time_span.parent.name == "a":
                            href = time_span.parent.get("href")
                            if href:
                                # Make absolute URL if needed
                                if href.startswith("/"):
                                    booking_url = f"{self.BASE_URL}{href}"
                                else:
                                    booking_url = href

                        showing = RawShowing(
                            title=title,
                            start_time=start_time,
                            booking_url=booking_url,
                        )
                        showings.append(showing)
                        logger.debug(f"Added: {title} at {start_time}")

                    except Exception as e:
                        logger.warning(f"Failed to parse time '{time_text}': {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to parse film container: {e}")
                continue

        return showings
