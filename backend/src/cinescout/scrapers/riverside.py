"""Riverside Studios cinema scraper using the Spektrix API v3."""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
SPEKTRIX_BASE = "https://system.spektrix.com/riversidestudios/api/v3"
CINEMA_PAGE = "https://www.riversidestudios.co.uk/whats-on/cinema/"


class RiversideScraper(BaseScraper):
    """
    Scraper for Riverside Studios cinema.

    Flow:
    1. Fetch all Cinema-type events from Spektrix to build an event_id → title/year map.
    2. Fetch instances for the requested date range from Spektrix.
    3. Filter instances to those in the cinema event map, skipping cancelled ones.
    """

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
                event_map = await self._fetch_cinema_events(client)
                if not event_map:
                    logger.warning("Riverside Studios: no cinema events returned")
                    return []
                showings = await self._fetch_instances(client, date_from, date_to, event_map)
        except Exception as e:
            logger.error(f"Riverside Studios scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Riverside Studios: found {len(showings)} showings")
        return showings

    async def _fetch_cinema_events(
        self, client: httpx.AsyncClient
    ) -> dict[str, dict[str, int | str | None]]:
        """Return {event_id: {title, year}} for all Cinema-type events."""
        r = await client.get(
            f"{SPEKTRIX_BASE}/events",
            params={"attribute_EventType": "Cinema"},
        )
        if r.status_code != 200:
            logger.warning(f"Riverside Studios: /events returned {r.status_code}")
            return {}

        event_map: dict[str, dict[str, int | str | None]] = {}
        for event in r.json():
            event_id = event.get("id")
            name = event.get("name", "")
            if not event_id or not name:
                continue
            year: int | None = None
            year_str = event.get("attribute_YearOfRelease", "")
            if year_str:
                try:
                    year = int(year_str)
                except ValueError:
                    pass
            event_map[event_id] = {
                "title": self.normalise_title(name),
                "year": year,
            }
        return event_map

    async def _fetch_instances(
        self,
        client: httpx.AsyncClient,
        date_from: date,
        date_to: date,
        event_map: dict[str, dict[str, int | str | None]],
    ) -> list[RawShowing]:
        r = await client.get(
            f"{SPEKTRIX_BASE}/instances",
            params={
                "startFrom": date_from.isoformat(),
                "startUntil": date_to.isoformat(),
            },
        )
        if r.status_code != 200:
            logger.warning(f"Riverside Studios: /instances returned {r.status_code}")
            return []

        showings: list[RawShowing] = []
        for instance in r.json():
            if instance.get("cancelled"):
                continue
            event_id = instance.get("event", {}).get("id", "")
            if event_id not in event_map:
                continue
            starts_at = instance.get("start", "")
            if not starts_at:
                continue
            try:
                start_time = datetime.fromisoformat(starts_at)
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=LONDON_TZ)
            except ValueError:
                continue

            # Spektrix API doesn't reliably respect startUntil — filter explicitly
            if not (date_from <= start_time.date() <= date_to):
                continue

            event = event_map[event_id]
            showings.append(
                RawShowing(
                    title=str(event["title"]),
                    start_time=start_time,
                    booking_url=CINEMA_PAGE,
                    year=int(event["year"]) if isinstance(event["year"], int) else None,
                )
            )

        return showings
