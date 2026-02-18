"""Everyman Cinemas scraper using their internal Gatsby/Boxoffice API.

Everyman uses a Movio Boxoffice (Vista Group) ticketing system. The frontend
is a Gatsby SPA on Netlify that calls unauthenticated Netlify Function routes
to fetch schedule and movie data at runtime.

Strategy (two-phase fetch):
  1. GET /schedule?theaters=…&from=…&to=…  — all sessions for this theater
     in the date window. Returns sessions grouped by movie ID then date, with
     exact start times, format/accessibility tags, and booking URLs.
  2. GET /movies?ids=…  for each unique movie ID concurrently. Provides the
     canonical title and director names.

Booking URLs come from the "default" provider in each session's ticketing list:
  https://purchase.everymancinema.com/launch/ticketing/{uuid}
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

_API_BASE = "https://www.everymancinema.com/api/gatsby-source-boxofficeapi"
_SCHEDULE_URL = f"{_API_BASE}/schedule"
_MOVIES_URL = f"{_API_BASE}/movies"

_CONCURRENCY = 10

# Strips surrounding straight or curly quotation marks from titles
_OUTER_QUOTES_RE = re.compile(r'^["\u201c\u2018](.+)["\u201d\u2019]$')

# Session tag suffix → format tag label.
# Tags follow "Category.Subcategory.Value" convention; we match on the suffix.
_SESSION_TAG_MAP: dict[str, str] = {
    "Accessibility.AudioDescribed": "AD",
    "Accessibility.BSLInterpreted": "BSL",
    "Accessibility.Subtitled": "Subtitled",
    "Accessibility.Relaxed": "Relaxed",
    "Projection.Film": "35mm",
    "Projection.IMAX": "IMAX",
    "Projection.4DX": "4DX",
    "Projection.ScreenX": "ScreenX",
}


def _format_tags(tags: list[str]) -> str | None:
    labels = []
    for tag in tags:
        for suffix, label in _SESSION_TAG_MAP.items():
            if tag.endswith(suffix):
                labels.append(label)
                break
    return ", ".join(labels) if labels else None


def _booking_url(session: dict) -> str | None:
    for entry in session.get("data", {}).get("ticketing", []):
        if entry.get("provider") == "default":
            urls = entry.get("urls", [])
            if urls:
                return urls[0]
    return None


class EverymanScraper(BaseScraper):
    """Scraper for an individual Everyman Cinemas venue."""

    def __init__(self, theater_id: str) -> None:
        self.theater_id = theater_id

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from the Everyman Boxoffice API."""
        try:
            timeout = httpx.Timeout(60.0)
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                showings = await self._fetch(client, date_from, date_to)
        except Exception as e:
            logger.error(f"Everyman ({self.theater_id}) scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Everyman ({self.theater_id}): found {len(showings)} showings")
        return showings

    async def _fetch(
        self, client: httpx.AsyncClient, date_from: date, date_to: date
    ) -> list[RawShowing]:
        # Phase 1: fetch schedule for this theater
        theater_json = json.dumps(
            {"id": self.theater_id, "timeZone": "Europe/London"},
            separators=(",", ":"),
        )
        resp = await client.get(
            _SCHEDULE_URL,
            params=[
                ("theaters", theater_json),
                ("from", date_from.isoformat()),
                ("to", date_to.isoformat()),
            ],
        )
        resp.raise_for_status()
        data = resp.json()

        theater_data = data.get(self.theater_id, {})
        schedule: dict[str, dict[str, list[dict]]] = theater_data.get("schedule", {})

        if not schedule:
            logger.debug(f"Everyman ({self.theater_id}): empty schedule")
            return []

        logger.debug(
            f"Everyman ({self.theater_id}): {len(schedule)} movies in schedule"
        )

        # Phase 2: fetch movie metadata concurrently
        sem = asyncio.Semaphore(_CONCURRENCY)
        movie_ids = list(schedule.keys())
        movie_tasks = [self._fetch_movie(client, sem, mid) for mid in movie_ids]
        movie_results = await asyncio.gather(*movie_tasks, return_exceptions=True)

        movies: dict[str, dict] = {}
        for mid, result in zip(movie_ids, movie_results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Everyman ({self.theater_id}): error fetching movie {mid}: {result}"
                )
            elif result is not None:
                movies[mid] = result

        # Build showings
        showings: list[RawShowing] = []
        for movie_id, dates in schedule.items():
            movie = movies.get(movie_id)
            if not movie:
                continue

            raw_title: str = movie.get("title", "").strip()
            # Strip surrounding quotation marks (e.g. '"Wuthering Heights"')
            m = _OUTER_QUOTES_RE.match(raw_title)
            if m:
                raw_title = m.group(1).strip()
            title = self.normalise_title(raw_title)
            if not title or len(title) < 2:
                continue

            for date_str, sessions in dates.items():
                for session in sessions:
                    showing = self._parse_session(title, session, date_from, date_to)
                    if showing:
                        showings.append(showing)

        return showings

    async def _fetch_movie(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        movie_id: str,
    ) -> dict | None:
        async with sem:
            resp = await client.get(_MOVIES_URL, params={"ids": movie_id})
            resp.raise_for_status()
            movies: list[dict] = resp.json()
        return movies[0] if movies else None

    def _parse_session(
        self,
        title: str,
        session: dict,
        date_from: date,
        date_to: date,
    ) -> RawShowing | None:
        if session.get("isExpired"):
            return None

        start_str = session.get("startsAt", "")
        if not start_str:
            return None

        try:
            dt_naive = datetime.fromisoformat(start_str)
        except ValueError:
            return None

        if not (date_from <= dt_naive.date() <= date_to):
            return None

        start_time = dt_naive.replace(tzinfo=LONDON_TZ)
        tags: list[str] = session.get("tags", [])

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=_booking_url(session),
            screen_name=None,
            format_tags=_format_tags(tags),
            price=None,
        )
