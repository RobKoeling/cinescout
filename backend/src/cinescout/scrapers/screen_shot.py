"""Screen-Shot Brighton scraper.

screen-shot.co.uk aggregates alternative/pop-up film events across Brighton
and Sussex. It uses The Events Calendar WordPress REST API — the same format
as the Cinema Museum scraper — but each event carries a venue object that
identifies where the screening takes place.

The venue name is stored in screen_name so users can see the location.
Events at the Lewes Depot are skipped to avoid duplicating showings already
scraped by the DepotLewesScraper.
"""

import html
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

API_URL = "https://screen-shot.co.uk/wp-json/tribe/events/v1/events"
PER_PAGE = 50

# Venue names (lowercase substrings) to skip — scraped by their own scraper
_SKIP_VENUES: frozenset[str] = frozenset({"lewes depot", "the depot", "depot cinema"})


class ScreenShotScraper(BaseScraper):
    """
    Scraper for Screen-Shot Brighton.

    Uses The Events Calendar WordPress REST API.
    """

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            showings = await self._fetch_showings(date_from, date_to)
        except Exception as e:
            logger.error(f"Screen-Shot scraper error: {e}", exc_info=True)
            return []
        logger.info(f"Screen-Shot Brighton: Found {len(showings)} showings")
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
                            f"Screen-Shot: failed to parse event {event.get('id')}: {e}"
                        )

                total_pages = data.get("total_pages", 1)
                if page >= total_pages:
                    break
                page += 1

        return showings

    def _parse_event(
        self, event: dict, date_from: date, date_to: date
    ) -> list[RawShowing]:
        title_raw = html.unescape(event.get("title", ""))
        if not title_raw:
            return []

        # Skip non-screening categories (workshops, talks, etc.)
        categories = [c.get("slug", "") for c in (event.get("categories") or [])]
        if "workshops" in categories or "talks" in categories:
            return []

        # Venue — skip venues covered by the DepotLewesScraper
        venue_obj = event.get("venue") or {}
        venue_name: str = venue_obj.get("venue", "") or ""
        venue_lower = venue_name.lower()
        if any(skip in venue_lower for skip in _SKIP_VENUES):
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

        title = self.normalise_title(title_raw)
        if not title or len(title) < 2:
            return []

        booking_url = event.get("url") or None

        price: float | None = None
        cost_details = event.get("cost_details") or {}
        values = cost_details.get("values", [])
        if values:
            try:
                price = float(values[0])
            except (ValueError, TypeError):
                pass

        return [
            RawShowing(
                title=title,
                start_time=start_time,
                booking_url=booking_url,
                screen_name=venue_name or None,
                price=price,
            )
        ]
