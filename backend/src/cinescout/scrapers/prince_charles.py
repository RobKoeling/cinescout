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

        # Look for film containers - try multiple selector patterns
        film_containers = (
            soup.find_all("div", class_=re.compile(r"film", re.I))
            or soup.find_all("article", class_=re.compile(r"film|post", re.I))
        )

        for container in film_containers:
            try:
                # Extract film title
                title_elem = (
                    container.find(["h2", "h3", "h4"], class_=re.compile(r"title|name", re.I))
                    or container.find("a", href=re.compile(r"/film/\d+/"))
                    or container.find(["h2", "h3", "h4"])
                )

                if not title_elem:
                    continue

                title = self.normalise_title(title_elem.get_text(strip=True))
                if not title or len(title) < 2:
                    continue

                # Find booking links with times
                # Pattern: "Book 5:45 pm" or similar
                booking_links = container.find_all("a", class_=re.compile(r"book|btn|time", re.I))

                if not booking_links:
                    # Try finding any links with "booknow" in href
                    booking_links = container.find_all("a", href=re.compile(r"booknow"))

                for link in booking_links:
                    try:
                        link_text = link.get_text(strip=True)
                        booking_url = link.get("href")

                        # Extract time from link text
                        # Patterns: "Book 5:45 pm", "5:45 pm", "17:45"
                        time_match = re.search(r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b', link_text, re.IGNORECASE)
                        if not time_match:
                            continue

                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        am_pm = time_match.group(3)

                        # Convert to 24-hour format if needed
                        if am_pm:
                            if am_pm.lower() == 'pm' and hour != 12:
                                hour += 12
                            elif am_pm.lower() == 'am' and hour == 12:
                                hour = 0

                        # Try to extract date from surrounding context
                        # Look for date indicators in parent elements
                        date_elem = container.find_previous(text=re.compile(r'\b\d{1,2}(?:st|nd|rd|th)?\s+\w+\b'))
                        showing_date = date_from  # Default

                        if date_elem:
                            # Try to parse date like "Friday 30th January" or "30 Jan"
                            date_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\b', str(date_elem))
                            if date_match:
                                day = int(date_match.group(1))
                                month_str = date_match.group(2)
                                month_map = {
                                    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
                                    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
                                    'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
                                    'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                                    'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
                                    'dec': 12, 'december': 12
                                }
                                month = month_map.get(month_str.lower(), date_from.month)
                                year = date_from.year
                                try:
                                    showing_date = date(year, month, day)
                                except ValueError:
                                    showing_date = date_from

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

                        # Make booking URL absolute if needed
                        if booking_url and not booking_url.startswith('http'):
                            booking_url = f"{self.BASE_URL}{booking_url}"

                        showing = RawShowing(
                            title=title,
                            start_time=start_time,
                            booking_url=booking_url,
                        )
                        showings.append(showing)
                        logger.debug(f"Parsed: {title} at {start_time}")

                    except Exception as e:
                        logger.warning(f"Failed to parse booking link: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to parse film container: {e}")
                continue

        return showings
