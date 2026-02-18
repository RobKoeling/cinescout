"""Cinema Museum scraper using The Events Calendar REST API."""

import html
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing
from cinescout.utils.text import split_double_bill

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

API_URL = "https://cinemamuseum.org.uk/wp-json/tribe/events/v1/events"
PER_PAGE = 50


class CinemaMuseumScraper(BaseScraper):
    """
    Scraper for the Cinema Museum (Kennington).

    Uses The Events Calendar WordPress REST API which returns structured JSON.
    """

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from the Cinema Museum API."""
        try:
            showings = await self._fetch_showings(date_from, date_to)
        except Exception as e:
            logger.error(f"Cinema Museum scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Cinema Museum: Found {len(showings)} showings")
        return showings

    async def _fetch_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        showings: list[RawShowing] = []

        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout, verify=False, follow_redirects=True
        ) as client:
            page = 1
            while True:
                params = {
                    "per_page": PER_PAGE,
                    "page": page,
                    "start_date": date_from.strftime("%Y-%m-%d 00:00:00"),
                    "end_date": date_to.strftime("%Y-%m-%d 23:59:59"),
                }
                r = await client.get(API_URL, params=params)
                r.raise_for_status()
                data = r.json()

                events = data.get("events", [])
                if not events:
                    break

                for event in events:
                    try:
                        showings.extend(self._parse_event(event, date_from, date_to))
                    except Exception as e:
                        logger.warning(
                            f"Cinema Museum: Failed to parse event {event.get('id')}: {e}"
                        )

                total_pages = data.get("total_pages", 1)
                if page >= total_pages:
                    break
                page += 1

        return showings

    def _parse_event(self, event: dict, date_from: date, date_to: date) -> list[RawShowing]:
        title_raw = html.unescape(event.get("title", ""))
        if not title_raw:
            return []

        # Skip non-screening events (tours, talks, etc.) by checking categories
        categories = [c.get("slug", "") for c in (event.get("categories") or [])]
        if "tours" in categories:
            return []

        # start_date is London local time ("2026-02-18 19:30:00")
        start_date_str = event.get("start_date", "")
        if not start_date_str:
            return []

        try:
            start_time = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=LONDON_TZ
            )
        except ValueError:
            return []

        if not (date_from <= start_time.date() <= date_to):
            return []

        # Event page URL is the best available booking link
        booking_url = event.get("url") or None

        # Price from cost_details (e.g. values: ["10"])
        price: float | None = None
        cost_details = event.get("cost_details") or {}
        values = cost_details.get("values", [])
        if values:
            try:
                price = float(values[0])
            except (ValueError, TypeError):
                pass

        # Split double bills: "Film A (1936) and Film B (1964)" → two showings
        titles = split_double_bill(title_raw)
        if len(titles) > 1:
            logger.debug(f"Cinema Museum: double bill split → {titles}")

        return [
            RawShowing(
                title=title,
                start_time=start_time,
                booking_url=booking_url,
                price=price,
            )
            for title in titles
            if title and len(title) >= 2
        ]
