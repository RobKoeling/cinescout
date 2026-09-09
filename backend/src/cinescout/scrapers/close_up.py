"""Close-Up Film Centre scraper."""

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

# The Close-Up website is behind an impenetrable Cloudflare managed challenge,
# so we scrape their TicketSource organiser page instead, which is server-rendered
# and publicly accessible with no bot protection.
TICKETSOURCE_URL = "https://www.ticketsource.co.uk/close-up-cinema"
TICKETSOURCE_BASE = "https://www.ticketsource.co.uk"


class CloseUpScraper(BaseScraper):
    """
    Scraper for Close-Up Film Centre (Shoreditch).

    Scrapes their TicketSource organiser listing page, which is server-rendered
    and contains all upcoming events with schema.org Event markup.
    """

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from Close-Up Film Centre via TicketSource."""
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout,
                verify=False,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
            ) as client:
                response = await client.get(TICKETSOURCE_URL)
                response.raise_for_status()
                showings = self._parse_html(response.text, date_from, date_to)
        except Exception as e:
            logger.error(f"Close-Up Film Centre scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Close-Up Film Centre: Found {len(showings)} showings")
        return showings

    def _parse_html(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        """Parse the TicketSource organiser page into RawShowings."""
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        for row in soup.select(".eventRow"):
            try:
                showing = self._parse_event_row(row, date_from, date_to)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(f"Close-Up Film Centre: Failed to parse event row: {e}")

        logger.debug(f"Close-Up Film Centre: {len(showings)} showings in date range")
        return showings

    def _parse_event_row(
        self, row: BeautifulSoup, date_from: date, date_to: date
    ) -> RawShowing | None:
        # Title
        title_elem = row.select_one("[itemprop='name']")
        if not title_elem:
            return None
        title = self.normalise_title(title_elem.get_text(strip=True))
        if not title or len(title) < 2:
            return None

        # Start time — schema.org content attribute is ISO 8601: "2026-03-27T20:15"
        date_elem = row.select_one("[itemprop='startDate']")
        if not date_elem or not date_elem.get("content"):
            return None
        try:
            start_dt = datetime.fromisoformat(date_elem["content"])
            start_time = start_dt.replace(tzinfo=LONDON_TZ)
        except ValueError:
            return None

        showing_date = start_time.date()
        if not (date_from <= showing_date <= date_to):
            return None

        # Booking URL
        booking_elem = row.select_one(".event-btn a[href]")
        booking_url: str | None = None
        if booking_elem:
            href = booking_elem["href"]
            booking_url = href if href.startswith("http") else f"{TICKETSOURCE_BASE}{href}"

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
        )
