"""The Nickel Cinema scraper using BeautifulSoup HTML parsing."""

import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
BASE_URL = "https://thenickel.co.uk"


class NickelScraper(BaseScraper):
    """
    Scraper for The Nickel Cinema (Clerkenwell).

    The homepage lists all upcoming screenings as individual card elements,
    each an <a href="/screening/[id]"> containing structured HTML paragraphs
    with the date ("Sunday 22.2"), doors time, film start time, and format.
    No JS rendering required — plain httpx + BeautifulSoup.
    """

    HOMEPAGE_URL = BASE_URL

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from The Nickel Cinema homepage."""
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout, follow_redirects=True
            ) as client:
                response = await client.get(self.HOMEPAGE_URL)
                response.raise_for_status()
                showings = self._parse_html(response.text, date_from, date_to)
        except Exception as e:
            logger.error(f"The Nickel scraper error: {e}", exc_info=True)
            return []

        logger.info(f"The Nickel: found {len(showings)} showings")
        return showings

    def _parse_html(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        """Parse screening cards from the homepage HTML."""
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []
        for card in soup.find_all("a", href=re.compile(r"^/screening/\d+")):
            if not isinstance(card, Tag):
                continue
            try:
                showing = self._parse_card(card, date_from, date_to)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(f"The Nickel: failed to parse card: {e}")
        return showings

    def _parse_card(self, card: Tag, date_from: date, date_to: date) -> RawShowing | None:
        """Parse a single screening card element into a RawShowing."""
        h3 = card.find("h3")
        if not h3:
            return None
        title = self.normalise_title(h3.get_text(strip=True))
        if not title:
            return None

        href = card.get("href", "")
        booking_url = f"{BASE_URL}{href}" if str(href).startswith("/") else str(href)

        # The date/time paragraph contains "Day DD.MM" — identify it by the DD.MM pattern
        datetime_text: str | None = None
        for p in card.find_all("p"):
            text = p.get_text(separator="\n", strip=True)
            if re.search(r"\d{1,2}\.\d{1,2}", text):
                datetime_text = text
                break

        if not datetime_text:
            return None

        lines = [line.strip() for line in datetime_text.split("\n") if line.strip()]
        if not lines:
            return None

        showing_date = self._parse_date(lines[0], date_from)
        if showing_date is None or not (date_from <= showing_date <= date_to):
            return None

        # Find the "Film HH:MMpm" line
        film_time_str: str | None = None
        for line in lines[1:]:
            if line.lower().startswith("film "):
                film_time_str = line[5:].strip()
                break

        if not film_time_str:
            return None

        time_parts = self._parse_time(film_time_str)
        if not time_parts:
            return None

        hour, minute = time_parts
        start_time = datetime(
            showing_date.year, showing_date.month, showing_date.day,
            hour, minute, tzinfo=LONDON_TZ,
        )

        # Format tag: last line of the block if it's a known projection format
        format_tag: str | None = None
        if lines and lines[-1].lower() in ("digital", "vhs", "35mm", "16mm"):
            format_tag = lines[-1]

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            format_tags=format_tag,
        )

    def _parse_date(self, text: str, reference_date: date) -> date | None:
        """
        Parse "Tuesday 17.2" or "Sunday 1.2" into a date object.

        Uses reference_date.year, rolling forward one year if the parsed
        date is more than 30 days before the reference (handles Dec → Jan).
        """
        m = re.search(r"(\d{1,2})\.(\d{1,2})", text)
        if not m:
            return None
        day, month = int(m.group(1)), int(m.group(2))
        try:
            candidate = date(reference_date.year, month, day)
        except ValueError:
            return None
        if (candidate - reference_date).days < -30:
            try:
                candidate = date(reference_date.year + 1, month, day)
            except ValueError:
                return None
        return candidate

    def _parse_time(self, text: str) -> tuple[int, int] | None:
        """Parse "6:30pm" or "8pm" into (hour, minute)."""
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text.strip(), re.IGNORECASE)
        if not m:
            return None
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        period = m.group(3).lower()
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        return hour, minute
