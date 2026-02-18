"""Lewes Depot Cinema scraper.

The site uses a Jacro WordPress plugin. The /whats-on/this-week page renders
static HTML (one upcoming showing per film). Each showing links to a lightweight
popup that returns the exact date, time, screen, and booking URL.

Strategy:
1. GET /whats-on/this-week  →  extract (title, slug, perf_id) per film box
2. GET perf-popup.php?id=X  →  extract exact datetime + booking URL
3. Filter results to the requested date range.
"""

import asyncio
import html as html_lib
import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

THIS_WEEK_URL = "https://lewesdepot.org/whats-on/this-week"
PERF_POPUP_BASE = "https://lewesdepot.org/wp-content/themes/lewesdepot/perf-popup.php"
BOOKING_BASE = "https://lewesdepot.org/film"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_CONCURRENCY = 10


class DepotLewesScraper(BaseScraper):
    """Scraper for Lewes Depot cinema."""

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            showings = await self._fetch_showings(date_from, date_to)
        except Exception as e:
            logger.error(f"Lewes Depot scraper error: {e}", exc_info=True)
            return []
        logger.info(f"Lewes Depot: Found {len(showings)} showings")
        return showings

    async def _fetch_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout,
            verify=False,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            r = await client.get(THIS_WEEK_URL)
            r.raise_for_status()
            entries = _parse_this_week(r.text)

            if not entries:
                logger.warning("Lewes Depot: no film entries found on this-week page")
                return []

            sem = asyncio.Semaphore(_CONCURRENCY)
            tasks = [
                _fetch_popup(client, sem, title, slug, perf_id)
                for title, slug, perf_id in entries
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        showings: list[RawShowing] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Lewes Depot: popup error: {result}")
                continue
            if result is not None and date_from <= result.start_time.date() <= date_to:
                showings.append(result)
        return showings


# ── helpers ──────────────────────────────────────────────────────────────────

_BOX_RE = re.compile(
    r'<div\s+class="col-md-4[^"]*live-event-box-sml[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
    re.DOTALL,
)
_TITLE_RE = re.compile(r'<strong>(.*?)</strong>', re.DOTALL)
_PERF_RE = re.compile(r'perf-popup\.php\?id=(\d+)')
_SLUG_RE = re.compile(r'href="/film/([^"/]+)"')


def _parse_this_week(html: str) -> list[tuple[str, str, str]]:
    """Return [(title, slug, perf_id), ...] from the this-week page."""
    entries: list[tuple[str, str, str]] = []
    for box in _BOX_RE.finditer(html):
        box_html = box.group(1)

        perf_match = _PERF_RE.search(box_html)
        if not perf_match:
            continue
        perf_id = perf_match.group(1)

        title_match = _TITLE_RE.search(box_html)
        if not title_match:
            continue
        title = html_lib.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()
        if not title:
            continue

        slug_match = _SLUG_RE.search(box_html)
        slug = slug_match.group(1) if slug_match else ""

        entries.append((title, slug, perf_id))
    return entries


async def _fetch_popup(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    title_fallback: str,
    slug: str,
    perf_id: str,
) -> RawShowing | None:
    async with sem:
        try:
            r = await client.get(PERF_POPUP_BASE, params={"id": perf_id})
            r.raise_for_status()
            popup_html = r.text
        except Exception as e:
            logger.warning(f"Lewes Depot: failed to fetch popup {perf_id}: {e}")
            return None

    return _parse_popup(popup_html, title_fallback, slug, perf_id)


def _parse_popup(
    popup_html: str,
    title_fallback: str,
    slug: str,
    perf_id: str,
) -> RawShowing | None:
    # Title
    tm = re.search(r'class="mb-ShortFilmTitle"[^>]*>(.*?)</h2>', popup_html, re.DOTALL)
    title = (
        html_lib.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        if tm
        else title_fallback
    )
    if not title or len(title) < 2:
        return None

    # Date and time
    # <h3 class="mb-PerformDate">Saturday 21 Feb <span class="mb-StartTime">1:00pm</span></h3>
    dm = re.search(
        r'class="mb-PerformDate">\s*(.*?)\s*<span[^>]*class="mb-StartTime"[^>]*>(.*?)</span>',
        popup_html,
        re.DOTALL,
    )
    if not dm:
        return None
    date_str = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", dm.group(1))).strip()
    time_str = dm.group(2).strip()

    start_time = _parse_depot_datetime(date_str, time_str)
    if start_time is None:
        logger.warning(f"Lewes Depot: cannot parse '{date_str} {time_str}' for '{title}'")
        return None

    # Booking URL
    bm = re.search(r'href="(https://lewesdepot\.org/film/[^"]+/booknow/[^"]+)"', popup_html)
    if bm:
        booking_url: str | None = bm.group(1)
    elif slug:
        booking_url = f"{BOOKING_BASE}/{slug}/booknow/{perf_id}"
    else:
        booking_url = None

    return RawShowing(
        title=title,
        start_time=start_time,
        booking_url=booking_url,
    )


def _parse_depot_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse "Saturday 21 Feb" + "1:00pm" into a timezone-aware datetime."""
    time_norm = time_str.strip().upper()  # "1:00PM"
    today = date.today()
    for year in (today.year, today.year + 1):
        try:
            dt = datetime.strptime(f"{date_str} {year} {time_norm}", "%A %d %b %Y %I:%M%p")
            dt = dt.replace(tzinfo=LONDON_TZ)
            # Accept if not more than 14 days in the past
            if dt.date() >= today - timedelta(days=14):
                return dt
        except ValueError:
            pass
    return None
