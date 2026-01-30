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
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
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

        # Find all jacro-event containers (one per film with multiple dates/times)
        jacro_events = soup.find_all("div", class_="jacro-event")

        logger.debug(f"Found {len(jacro_events)} jacro-event containers")

        for event in jacro_events:
            try:
                # Extract film title from the liveeventtitle link
                film_link = event.find("a", class_="liveeventtitle")
                if not film_link:
                    continue

                title_text = film_link.get_text(strip=True)
                title = self.normalise_title(title_text)

                if not title or len(title) < 2:
                    continue

                logger.debug(f"Processing film: {title}")

                # Find performance list containers
                perf_lists = event.find_all("ul", class_="performance-list-items")

                for perf_list in perf_lists:
                    try:
                        # Get all children in order (dates and li elements)
                        children = [c for c in perf_list.children if hasattr(c, 'name') and c.name]

                        current_date = None
                        month_map = {
                            'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
                            'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
                            'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
                            'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                            'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
                            'dec': 12, 'december': 12
                        }

                        for child in children:
                            # Check if this is a date heading
                            if child.name == 'div' and 'heading' in child.get('class', []):
                                date_text = child.get_text(strip=True)
                                date_match = re.search(
                                    r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\b',
                                    date_text
                                )
                                if date_match:
                                    day = int(date_match.group(1))
                                    month_str = date_match.group(2)
                                    month = month_map.get(month_str.lower())

                                    if month:
                                        year = date_from.year
                                        try:
                                            showing_date = date(year, month, day)
                                            # Check if date is in range
                                            if date_from <= showing_date <= date_to:
                                                current_date = showing_date
                                                logger.debug(f"  Date: {showing_date}")
                                            else:
                                                current_date = None
                                        except ValueError:
                                            current_date = None

                            # Check if this is a time li element
                            elif child.name == 'li' and current_date:
                                time_span = child.find("span", class_="time")
                                if time_span:
                                    try:
                                        time_text = time_span.get_text(strip=True)

                                        # Parse time (format: "5:45 pm")
                                        time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
                                        if not time_match:
                                            continue

                                        hour = int(time_match.group(1))
                                        minute = int(time_match.group(2))

                                        # Handle AM/PM
                                        if "pm" in time_text.lower() and hour != 12:
                                            hour += 12
                                        elif "am" in time_text.lower() and hour == 12:
                                            hour = 0

                                        start_time = datetime(
                                            current_date.year,
                                            current_date.month,
                                            current_date.day,
                                            hour,
                                            minute,
                                            tzinfo=LONDON_TZ,
                                        )

                                        # Try to find booking URL
                                        booking_url = None
                                        if time_span.parent and time_span.parent.name == "a":
                                            href = time_span.parent.get("href")
                                            if href:
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
                                        logger.debug(f"  Added: {title} at {start_time}")

                                    except Exception as e:
                                        logger.warning(f"Failed to parse time '{time_text}': {e}")
                                        continue

                    except Exception as e:
                        logger.warning(f"Failed to parse performance list: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to parse jacro-event: {e}")
                continue

        return showings
