"""Coldharbour Blue Cinema scraper (formerly Whirled Cinema, Brixton)."""

import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")


class ColdharbourBlueScraper(BaseScraper):
    """
    Scraper for Coldharbour Blue Cinema (Brixton).

    Uses the Tribe Events WordPress REST API. Only events in the
    'screenings' category are included — the venue also hosts live music,
    workshops, etc.
    """

    BASE_URL = "https://www.coldharbourblue.com"
    EVENTS_API_URL = f"{BASE_URL}/wp-json/tribe/events/v1/events"
    SCREENINGS_SLUG = "screenings"

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from Coldharbour Blue Cinema."""
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout, verify=False, follow_redirects=True
            ) as client:
                events = await self._fetch_all_events(client, date_from, date_to)
                showings = self._parse_events(events, date_from, date_to)
        except Exception as e:
            logger.error(f"Coldharbour Blue scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Coldharbour Blue: Found {len(showings)} showings")
        return showings

    async def _fetch_all_events(
        self,
        client: httpx.AsyncClient,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Fetch all events from the Tribe Events API, paginating as needed."""
        events: list[dict] = []
        url: str | None = self.EVENTS_API_URL
        params: dict | None = {
            "start_date": date_from.strftime("%Y-%m-%d 00:00:00"),
            "end_date": date_to.strftime("%Y-%m-%d 23:59:59"),
            "per_page": 50,
        }

        while url:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Coldharbour Blue: API returned {response.status_code} for {url}")
                break

            data = response.json()
            events.extend(data.get("events", []))
            logger.debug(
                f"Coldharbour Blue: Fetched page, total so far: {len(events)}"
            )

            # next_rest_url already includes query params for pagination
            url = data.get("next_rest_url") or None
            params = None  # Params are baked into next_rest_url

        return events

    def _parse_events(
        self, events: list[dict], date_from: date, date_to: date
    ) -> list[RawShowing]:
        """Filter to screenings only and parse into RawShowings."""
        showings: list[RawShowing] = []

        for event in events:
            try:
                # Skip non-screening events (live music, workshops, etc.)
                category_slugs = {c.get("slug", "") for c in event.get("categories", [])}
                if self.SCREENINGS_SLUG not in category_slugs:
                    continue

                showing = self._parse_event(event, date_from, date_to)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(f"Coldharbour Blue: Failed to parse event: {e}")

        return showings

    def _parse_event(
        self, event: dict, date_from: date, date_to: date
    ) -> RawShowing | None:
        title_raw = event.get("title", "")
        if not title_raw:
            return None

        title = self.normalise_title(str(title_raw))
        if not title or len(title) < 2:
            return None

        # start_date format: "2026-03-24 20:00:00"
        start_date_str = event.get("start_date", "")
        if not start_date_str:
            return None

        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

        showing_date = start_dt.date()
        if not (date_from <= showing_date <= date_to):
            return None

        start_time = start_dt.replace(tzinfo=LONDON_TZ)

        booking_url: str | None = event.get("url") or None

        # Parse price from "£10.00" format
        price: float | None = None
        cost = event.get("cost", "")
        if cost:
            price_match = re.search(r"[\d.]+", str(cost))
            if price_match:
                try:
                    price = float(price_match.group())
                except ValueError:
                    pass

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            price=price,
        )
