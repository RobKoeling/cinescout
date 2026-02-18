"""The Castle Cinema (Homerton, Hackney) scraper.

The Castle Cinema is a server-rendered Django-style site with no JSON API.
However, every programme page embeds machine-readable Schema.org
``ScreeningEvent`` JSON-LD blocks — the cleanest possible data source.

Strategy (two-phase fetch):
  1. GET /listings  — parses all /programme/{id}/{slug}/ hrefs to get the
     current programme.
  2. GET each programme page concurrently — extracts ScreeningEvent JSON-LD
     blocks with startDate, booking URL, and film title.

Booking URL: https://thecastlecinema.com/bookings/{perfCode}/
             (the ``@id`` field in the ScreeningEvent JSON-LD)
"""

import asyncio
import json
import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
BASE_URL = "https://thecastlecinema.com"
LISTINGS_URL = f"{BASE_URL}/listings"

_CONCURRENCY = 8
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_PROGRAMME_RE = re.compile(r"/programme/\d+/[^\s\"'<>]+")
_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


class CastleScraper(BaseScraper):
    """Scraper for The Castle Cinema, Homerton."""

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                verify=False,
                headers=_HEADERS,
                follow_redirects=True,
            ) as client:
                showings = await self._fetch(client, date_from, date_to)
        except Exception as e:
            logger.error(f"Castle scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Castle: found {len(showings)} showings")
        return showings

    async def _fetch(
        self, client: httpx.AsyncClient, date_from: date, date_to: date
    ) -> list[RawShowing]:
        # Phase 1: get programme list
        resp = await client.get(LISTINGS_URL)
        resp.raise_for_status()
        prog_paths = list(dict.fromkeys(_PROGRAMME_RE.findall(resp.text)))
        logger.debug(f"Castle: {len(prog_paths)} programmes found")

        if not prog_paths:
            return []

        # Phase 2: fetch each programme page concurrently
        sem = asyncio.Semaphore(_CONCURRENCY)
        tasks = [self._fetch_programme(client, sem, path) for path in prog_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        showings: list[RawShowing] = []
        for path, result in zip(prog_paths, results):
            if isinstance(result, Exception):
                logger.warning(f"Castle: error fetching {path}: {result}")
                continue
            for showing in result:
                if date_from <= showing.start_time.date() <= date_to:
                    showings.append(showing)

        return showings

    async def _fetch_programme(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        path: str,
    ) -> list[RawShowing]:
        async with sem:
            resp = await client.get(f"{BASE_URL}{path}")
            resp.raise_for_status()

        showings: list[RawShowing] = []
        for block in _JSONLD_RE.findall(resp.text):
            try:
                obj = json.loads(block)
            except json.JSONDecodeError:
                continue

            if obj.get("@type") != "ScreeningEvent":
                continue

            showing = self._parse_event(obj)
            if showing:
                showings.append(showing)

        return showings

    def _parse_event(self, obj: dict) -> RawShowing | None:
        start_str: str = obj.get("startDate", "")
        if not start_str:
            return None

        try:
            dt_naive = datetime.fromisoformat(start_str)
        except ValueError:
            return None

        start_time = dt_naive.replace(tzinfo=LONDON_TZ)

        # Title: prefer workPresented.name, fall back to event name
        work = obj.get("workPresented") or {}
        raw_title: str = work.get("name") or obj.get("name", "")
        raw_title = raw_title.strip()
        title = self.normalise_title(raw_title)
        if not title or len(title) < 2:
            return None

        # Booking URL is the @id of the ScreeningEvent
        booking_url: str | None = obj.get("@id") or obj.get("url") or None

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            screen_name=None,
            format_tags=None,
            price=None,
        )
