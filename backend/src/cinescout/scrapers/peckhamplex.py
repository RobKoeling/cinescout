"""Peckhamplex scraper using their public JSON API.

Peckhamplex uses Veezi for ticketing and provides a clean unauthenticated
JSON API that returns all films with their complete showtimes.

Strategy:
  GET /api/v1/film/by/title  — returns all films grouped by title, each
  with an array of showings containing ISO 8601 timestamps and Veezi
  booking URLs.

Booking URL: https://ticketing.eu.veezi.com/purchase/{id}?siteToken=...
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
API_URL = "https://www.peckhamplex.london/api/v1/film/by/title"


class PeckhamplexScraper(BaseScraper):
    """Scraper for Peckhamplex (Peckham, South London)."""

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from the Peckhamplex JSON API."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(API_URL)
                resp.raise_for_status()
                showings = self._parse(resp.json(), date_from, date_to)
        except Exception as e:
            logger.error(f"Peckhamplex scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Peckhamplex: found {len(showings)} showings")
        return showings

    def _parse(
        self, data: dict, date_from: date, date_to: date
    ) -> list[RawShowing]:
        """Parse the API response into RawShowing objects.

        API returns: {"Film Title": {"Friday 20th...": [{showing}, ...], ...}, ...}
        """
        showings: list[RawShowing] = []

        for raw_title, date_groups in data.items():
            title = self.normalise_title(raw_title)
            if not title or len(title) < 2:
                continue

            # date_groups is {"Friday 20th February 2026": [showings], ...}
            for date_str, showing_list in date_groups.items():
                for showing_data in showing_list:
                    showing = self._parse_showing(title, showing_data, date_from, date_to)
                    if showing:
                        showings.append(showing)

        return showings

    def _parse_showing(
        self,
        title: str,
        showing_data: dict,
        date_from: date,
        date_to: date,
    ) -> RawShowing | None:
        """Parse a single showing from the API data."""
        # Date is ISO 8601: "2026-02-20T11:40:00.000000Z"
        date_str: str = showing_data.get("date", "")
        if not date_str:
            return None

        try:
            # Parse as UTC, convert to London time
            dt_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            start_time = dt_utc.astimezone(LONDON_TZ)
        except ValueError:
            return None

        if not (date_from <= start_time.date() <= date_to):
            return None

        booking_url: str | None = showing_data.get("url")

        # Format tags from special screening flags
        tags: list[str] = []
        if showing_data.get("autism"):
            tags.append("Autism Friendly")
        if showing_data.get("hoh"):
            tags.append("Hard of Hearing")
        if showing_data.get("wwb"):
            tags.append("Watch with Baby")

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            screen_name=None,
            format_tags=", ".join(tags) if tags else None,
            price=None,
        )
