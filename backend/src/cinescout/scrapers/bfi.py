"""BFI Southbank scraper."""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")


class BFIScraper(BaseScraper):
    """
    Scraper for BFI Southbank.

    Uses the BFI website's HTML structure to extract showings.
    """

    BASE_URL = "https://whatson.bfi.org.uk"

    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch showings from BFI Southbank."""
        showings: list[RawShowing] = []

        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout) as client:
                # BFI shows one day at a time
                current_date = date_from
                while current_date <= date_to:
                    date_showings = await self._scrape_date(client, current_date)
                    showings.extend(date_showings)
                    current_date = date(
                        current_date.year,
                        current_date.month,
                        current_date.day + 1,
                    )

        except Exception as e:
            logger.error(f"BFI scraper error: {e}", exc_info=True)
            return []

        logger.info(f"BFI: Found {len(showings)} showings")
        return showings

    async def _scrape_date(
        self,
        client: httpx.AsyncClient,
        showing_date: date,
    ) -> list[RawShowing]:
        """Scrape showings for a specific date."""
        # Format date for BFI URL
        date_str = showing_date.strftime("%Y-%m-%d")
        url = f"{self.BASE_URL}/Online/default.asp?BOparam::WScontent::loadArticle::permalink=whats-on&BOparam::WScontent::loadArticle::context_id=&date={date_str}"

        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch BFI for {date_str}: {e}")
            return []

        return self._parse_html(response.text, showing_date)

    def _parse_html(self, html: str, showing_date: date) -> list[RawShowing]:
        """Parse BFI HTML to extract showings."""
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        # BFI structure: find screening items
        # This is a simplified implementation - real BFI structure may vary
        # For MVP, we'll create a basic parser that can be refined
        screening_items = soup.find_all("div", class_="screening")

        for item in screening_items:
            try:
                # Extract title
                title_elem = item.find("h3", class_="title") or item.find("a", class_="title")
                if not title_elem:
                    continue
                title = self.normalise_title(title_elem.get_text(strip=True))

                # Extract time
                time_elem = item.find("span", class_="time")
                if not time_elem:
                    continue
                time_str = time_elem.get_text(strip=True)

                # Parse time (format: "18:30")
                try:
                    hour, minute = map(int, time_str.split(":"))
                    start_time = datetime(
                        showing_date.year,
                        showing_date.month,
                        showing_date.day,
                        hour,
                        minute,
                        tzinfo=LONDON_TZ,
                    )
                except ValueError:
                    logger.warning(f"Invalid time format: {time_str}")
                    continue

                # Extract booking URL
                booking_link = item.find("a", class_="book-button")
                booking_url = (
                    f"{self.BASE_URL}{booking_link['href']}"
                    if booking_link and booking_link.get("href")
                    else None
                )

                # Extract screen name
                screen_elem = item.find("span", class_="screen")
                screen_name = screen_elem.get_text(strip=True) if screen_elem else None

                showing = RawShowing(
                    title=title,
                    start_time=start_time,
                    booking_url=booking_url,
                    screen_name=screen_name,
                )
                showings.append(showing)

            except Exception as e:
                logger.warning(f"Failed to parse BFI screening item: {e}")
                continue

        return showings
