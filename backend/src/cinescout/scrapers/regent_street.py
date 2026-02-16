"""Regent Street Cinema scraper using their GraphQL API (no Playwright needed)."""

import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

BASE_URL = "https://www.regentstreetcinema.com"
GRAPHQL_URL = f"{BASE_URL}/graphql"

# Site ID and badge filter discovered from browser network traffic
_SITE_IDS = [85]
_ANY_BADGE_IDS = [1314]
_EVERY_BADGE_IDS = [None]

# Minimal query: only the fields we actually need
_DATES_QUERY = """
query ($ids: [ID], $movieId: ID, $movieIds: [ID], $titleClassId: ID, $titleClassIds: [ID],
       $siteIds: [ID], $everyShowingBadgeIds: [ID], $anyShowingBadgeIds: [ID]) {
  datesWithShowing(
    ids: $ids movieId: $movieId movieIds: $movieIds
    titleClassId: $titleClassId titleClassIds: $titleClassIds
    siteIds: $siteIds everyShowingBadgeIds: $everyShowingBadgeIds
    anyShowingBadgeIds: $anyShowingBadgeIds
  ) { value }
}
"""

_SHOWINGS_QUERY = """
query ($date: String, $ids: [ID], $movieId: ID, $movieIds: [ID], $titleClassId: ID,
       $titleClassIds: [ID], $siteIds: [ID], $everyShowingBadgeIds: [ID],
       $anyShowingBadgeIds: [ID], $resultVersion: String) {
  showingsForDate(
    date: $date ids: $ids movieId: $movieId movieIds: $movieIds
    titleClassId: $titleClassId titleClassIds: $titleClassIds
    siteIds: $siteIds everyShowingBadgeIds: $everyShowingBadgeIds
    anyShowingBadgeIds: $anyShowingBadgeIds resultVersion: $resultVersion
  ) {
    data {
      id
      time
      movie { name urlSlug }
    }
  }
}
"""

_BASE_VARIABLES: dict = {
    "ids": [],
    "movieId": None,
    "movieIds": [],
    "titleClassId": None,
    "titleClassIds": [],
    "siteIds": _SITE_IDS,
    "anyShowingBadgeIds": _ANY_BADGE_IDS,
    "everyShowingBadgeIds": _EVERY_BADGE_IDS,
}


class RegentStreetScraper(BaseScraper):
    """
    Scraper for Regent Street Cinema.

    The site runs on a custom SPA that uses a GraphQL API.  We call it
    directly via httpx — no browser needed.

    Discovery method: captured request/response pairs from browser DevTools
    while loading https://www.regentstreetcinema.com/choose-day/.
    """

    BASE_URL = BASE_URL

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from Regent Street Cinema."""
        try:
            showings = await self._fetch_showings(date_from, date_to)
        except Exception as e:
            logger.error(f"Regent Street Cinema scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Regent Street Cinema: Found {len(showings)} showings")
        return showings

    async def _fetch_showings(
        self, date_from: date, date_to: date
    ) -> list[RawShowing]:
        # Custom headers required by the API (discovered via browser DevTools)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/graphql-response+json,application/json;q=0.9",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/choose-day/",
            "circuit-id": "19",
            "site-id": "85",
            "client-type": "consumer",
            "is-electron-mode": "false",
        }

        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout, verify=False
        ) as client:
            showing_dates = await self._fetch_dates(client, headers)
            logger.debug(
                f"Regent Street: {len(showing_dates)} dates with showings: {showing_dates}"
            )

            if not showing_dates:
                return []

            # Filter to the requested range
            target_dates = [
                d for d in showing_dates if date_from <= d <= date_to
            ]
            logger.debug(
                f"Regent Street: {len(target_dates)} dates in requested range"
            )

            showings: list[RawShowing] = []
            for show_date in target_dates:
                day_showings = await self._fetch_for_date(
                    client, headers, show_date
                )
                showings.extend(day_showings)

        return showings

    async def _fetch_dates(
        self, client: httpx.AsyncClient, headers: dict
    ) -> list[date]:
        """Return all dates that have at least one showing."""
        payload = {
            "variables": {**_BASE_VARIABLES},
            "query": _DATES_QUERY,
        }
        r = await client.post(GRAPHQL_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

        raw_value = (
            data.get("data", {})
            .get("datesWithShowing", {})
            .get("value", "[]")
        )
        try:
            date_strings: list[str] = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                f"Regent Street: Could not parse datesWithShowing value: {raw_value!r}"
            )
            return []

        dates: list[date] = []
        for ds in date_strings:
            try:
                dates.append(date.fromisoformat(ds))
            except ValueError:
                logger.debug(f"Regent Street: Skipping invalid date string: {ds!r}")

        return dates

    async def _fetch_for_date(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        show_date: date,
    ) -> list[RawShowing]:
        payload = {
            "variables": {
                **_BASE_VARIABLES,
                "date": show_date.isoformat(),
                "resultVersion": None,
            },
            "query": _SHOWINGS_QUERY,
        }
        r = await client.post(GRAPHQL_URL, json=payload, headers=headers)
        if r.status_code != 200:
            logger.warning(
                f"Regent Street: showingsForDate({show_date}) returned {r.status_code}"
            )
            return []

        data_list = (
            r.json()
            .get("data", {})
            .get("showingsForDate", {})
            .get("data", [])
        )

        showings: list[RawShowing] = []
        for item in data_list:
            try:
                showing = self._parse_showing(item)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(
                    f"Regent Street: Failed to parse showing {item.get('id')}: {e}"
                )

        return showings

    def _parse_showing(self, item: dict) -> RawShowing | None:
        showing_id = item.get("id", "")
        time_str = item.get("time", "")
        movie = item.get("movie") or {}

        title_raw = movie.get("name", "")
        if not title_raw or not showing_id or not time_str:
            return None

        title = self.normalise_title(title_raw)
        if not title or len(title) < 2:
            return None

        try:
            start_time = datetime.fromisoformat(time_str)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=LONDON_TZ)
        except ValueError:
            return None

        url_slug = movie.get("urlSlug") or ""
        booking_url = (
            f"{BASE_URL}/checkout/showing/{url_slug}/{showing_id}/"
            if url_slug
            else f"{BASE_URL}/checkout/showing/{showing_id}/"
        )

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
        )
