"""Barbican Centre cinema scraper using the Spektrix JSON API.

The Barbican uses Spektrix for ticketing, which exposes a public REST API
with no authentication required.

Strategy (two-phase fetch):
  1. GET /instances?startFrom=…&startTo=…  — all event instances in the date
     window (~300 records, ~4 seconds).  Gives exact start times, accessibility
     flags and instance IDs, grouped by event ID.
  2. GET /events/{id} for each unique event ID concurrently (typically ~10-50
     cinema events in a 1-week window).  Filters to
     attribute_PrimaryArtForm == "Cinema" and provides the canonical title.

Booking URLs are constructed from the webInstanceId field when present:
  https://tickets.barbican.org.uk/choose-seats/{webInstanceId}
"""

import asyncio
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

SPEKTRIX_BASE = "https://spektrix.barbican.org.uk/barbicancentre/api/v3"
INSTANCES_URL = f"{SPEKTRIX_BASE}/instances"
EVENT_URL = f"{SPEKTRIX_BASE}/events/{{event_id}}"
BOOKING_URL_BASE = "https://tickets.barbican.org.uk/choose-seats"

_CONCURRENCY = 10

# Accessibility flag → format tag label
_ACCESS_FLAGS: dict[str, str] = {
    "attribute_AudioDescribed": "AD",
    "attribute_BSL": "BSL",
    "attribute_Captioned": "Captioned",
    "attribute_Relaxed": "Relaxed",
}

# Strips a BBFC certificate from the end of a title: "(15)", "(12A)", "(U)", "(18*)"
_CERT_RE = re.compile(r"\s*\([0-9U][A-Z0-9*]*\)\s*$")

# Strips surrounding straight or curly quotation marks
_OUTER_QUOTES_RE = re.compile(r'^["\u201c\u2018](.+)["\u201d\u2019]$')


def _clean_title(raw: str) -> str:
    """Return a normalised film title from a Spektrix event name.

    Removes:
    - Leading/trailing whitespace
    - Surrounding quotation marks  ('"Wuthering Heights"' → 'Wuthering Heights')
    - Accessibility suffixes       ('(AD)', '(BSL)' — go into format_tags instead)
    - BBFC certificate suffix      ('(15)', '(12A)', '(U)')
    """
    title = raw.strip()
    # Strip accessibility abbreviation suffixes
    title = re.sub(r"\s*\((AD|BSL|CC|Captioned|Relaxed)\)\s*$", "", title).strip()
    # Strip BBFC cert
    title = _CERT_RE.sub("", title).strip()
    # Strip surrounding quotes
    m = _OUTER_QUOTES_RE.match(title)
    if m:
        title = m.group(1).strip()
    return title


def _format_tags(instance: dict) -> str | None:
    tags = [
        label
        for flag, label in _ACCESS_FLAGS.items()
        if instance.get(flag) is True
    ]
    return ", ".join(tags) if tags else None


class BarbicanScraper(BaseScraper):
    """Scraper for Barbican Centre cinema (London)."""

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from the Barbican Spektrix API."""
        try:
            # Use a longer timeout — the instances endpoint can be slow
            timeout = httpx.Timeout(60.0)
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                showings = await self._fetch(client, date_from, date_to)
        except Exception as e:
            logger.error(f"Barbican scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Barbican: found {len(showings)} showings")
        return showings

    async def _fetch(
        self, client: httpx.AsyncClient, date_from: date, date_to: date
    ) -> list[RawShowing]:
        # Phase 1: fetch all instances in the date window
        resp = await client.get(
            INSTANCES_URL,
            params={
                "startFrom": date_from.isoformat(),
                "startTo": date_to.isoformat(),
            },
        )
        resp.raise_for_status()
        instances: list[dict] = resp.json()
        logger.debug(f"Barbican: {len(instances)} instances in date window")

        # Group instances by event ID
        by_event: dict[str, list[dict]] = {}
        for inst in instances:
            event_id = inst.get("event", {}).get("id")
            if event_id:
                by_event.setdefault(event_id, []).append(inst)

        if not by_event:
            return []

        # Phase 2: fetch event details concurrently, filter to cinema
        sem = asyncio.Semaphore(_CONCURRENCY)
        event_tasks = [
            self._fetch_event(client, sem, event_id)
            for event_id in by_event
        ]
        event_results = await asyncio.gather(*event_tasks, return_exceptions=True)

        showings: list[RawShowing] = []
        for event_id, result in zip(by_event.keys(), event_results):
            if isinstance(result, Exception):
                logger.warning(f"Barbican: error fetching event {event_id}: {result}")
                continue
            if result is None:
                continue  # not a cinema event
            event = result

            raw_name: str = event.get("name", "").strip()
            title = self.normalise_title(_clean_title(raw_name))
            if not title or len(title) < 2:
                continue

            for inst in by_event[event_id]:
                showing = self._parse_instance(title, inst, date_from, date_to)
                if showing:
                    showings.append(showing)

        return showings

    async def _fetch_event(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        event_id: str,
    ) -> dict | None:
        """Fetch event details; return None if not a cinema event."""
        async with sem:
            resp = await client.get(EVENT_URL.format(event_id=event_id))
            resp.raise_for_status()
            event: dict = resp.json()

        if event.get("attribute_PrimaryArtForm") != "Cinema":
            return None
        return event

    def _parse_instance(
        self,
        title: str,
        inst: dict,
        date_from: date,
        date_to: date,
    ) -> RawShowing | None:
        if inst.get("cancelled"):
            return None

        start_str = inst.get("start", "")
        if not start_str:
            return None

        try:
            dt_naive = datetime.fromisoformat(start_str)
        except ValueError:
            return None

        if not (date_from <= dt_naive.date() <= date_to):
            return None

        start_time = dt_naive.replace(tzinfo=LONDON_TZ)

        # webInstanceId is always null in the Spektrix API response; fall back to
        # the numeric prefix of the instance id (e.g. "3331003AXXX…" → "3331003")
        # which maps directly to https://tickets.barbican.org.uk/choose-seats/{id}
        web_id = inst.get("webInstanceId")
        if not web_id:
            instance_id = inst.get("id", "")
            m = re.match(r"^(\d+)", instance_id)
            if m:
                web_id = m.group(1)
        booking_url: str | None = (
            f"{BOOKING_URL_BASE}/{web_id}" if web_id else None
        )

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            screen_name=None,
            format_tags=_format_tags(inst),
            price=None,
        )
