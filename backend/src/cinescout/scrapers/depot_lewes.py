"""Lewes Depot Cinema scraper.

The site uses a Jacro WordPress plugin. Three-step HTTP approach — no Playwright needed:

1. GET /whats-on/this-week → static HTML listing every film showing this week.
   We extract unique /film/{slug} hrefs from the page (simple, robust).

2. GET /film/{slug} → the film's own page embeds booking URLs for *all* upcoming
   performances (pattern: .../booknow/{perf_id}).

3. GET perf-popup.php?id={perf_id} → exact date, time, screen, booking URL.

Non-screening events (workshops, wine tastings, music events) are excluded via
slug keyword filtering before we make any network requests for them.
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
FILM_PAGE_BASE = "https://lewesdepot.org/film"
PERF_POPUP_BASE = "https://lewesdepot.org/wp-content/themes/lewesdepot/perf-popup.php"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_CONCURRENCY = 10

# Slug substrings that identify non-film events to skip
_NON_FILM_SLUG_PARTS: tuple[str, ...] = (
    "workshop",
    "wine-tasting",
    "wine-",
    "music-with-",
    "tasting",
    "screenwriting",
)


def _is_film_slug(slug: str) -> bool:
    return not any(part in slug for part in _NON_FILM_SLUG_PARTS)


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
            # Step 1: get all unique film slugs from the this-week page
            r = await client.get(THIS_WEEK_URL)
            r.raise_for_status()
            slugs = _extract_film_slugs(r.text)
            if not slugs:
                logger.warning("Lewes Depot: no film slugs found on this-week page")
                return []
            logger.debug(f"Lewes Depot: found {len(slugs)} film slugs")

            # Step 2: for each film slug, fetch its page to get all perf IDs
            sem = asyncio.Semaphore(_CONCURRENCY)
            film_page_tasks = [
                _fetch_film_perf_ids(client, sem, slug)
                for slug in slugs
            ]
            film_perf_lists = await asyncio.gather(*film_page_tasks, return_exceptions=True)

            # Flatten to (slug, perf_id, booking_url) — deduplicate across films
            perf_entries: list[tuple[str, str, str | None]] = []
            seen_perf_ids: set[str] = set()
            for i, result in enumerate(film_perf_lists):
                if isinstance(result, Exception):
                    logger.warning(f"Lewes Depot: film page error for {slugs[i]}: {result}")
                    continue
                for perf_id, booking_url in result:
                    if perf_id not in seen_perf_ids:
                        seen_perf_ids.add(perf_id)
                        perf_entries.append((slugs[i], perf_id, booking_url))

            if not perf_entries:
                return []
            logger.debug(f"Lewes Depot: {len(perf_entries)} unique perf IDs to fetch")

            # Step 3: fetch popup for each perf_id to get exact date/time
            popup_tasks = [
                _fetch_popup(client, sem, slug, perf_id, booking_url)
                for slug, perf_id, booking_url in perf_entries
            ]
            results = await asyncio.gather(*popup_tasks, return_exceptions=True)

        showings: list[RawShowing] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Lewes Depot: popup error: {result}")
                continue
            if result is not None and date_from <= result.start_time.date() <= date_to:
                showings.append(result)
        return showings


# ── helpers ───────────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r'href="/film/([^"/]+)"')
_BOOKNOW_RE = re.compile(r'href="(https://lewesdepot\.org/film/[^"]+/booknow/(\d+))"')


def _extract_film_slugs(html: str) -> list[str]:
    """Return unique film slugs from the this-week page, filtering non-film events."""
    seen: set[str] = set()
    slugs: list[str] = []
    for slug in _SLUG_RE.findall(html):
        if slug not in seen and _is_film_slug(slug):
            seen.add(slug)
            slugs.append(slug)
    return slugs


async def _fetch_film_perf_ids(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    slug: str,
) -> list[tuple[str, str | None]]:
    """Return [(perf_id, booking_url), ...] from a film's own page."""
    async with sem:
        try:
            r = await client.get(f"{FILM_PAGE_BASE}/{slug}")
            r.raise_for_status()
            html = r.text
        except Exception as e:
            logger.warning(f"Lewes Depot: failed to fetch film page '{slug}': {e}")
            return []

    entries: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for booking_url, perf_id in _BOOKNOW_RE.findall(html):
        if perf_id not in seen:
            seen.add(perf_id)
            entries.append((perf_id, booking_url))
    return entries


async def _fetch_popup(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    slug: str,
    perf_id: str,
    booking_url_fallback: str | None,
) -> RawShowing | None:
    async with sem:
        try:
            r = await client.get(PERF_POPUP_BASE, params={"id": perf_id})
            r.raise_for_status()
            popup_html = r.text
        except Exception as e:
            logger.warning(f"Lewes Depot: failed to fetch popup {perf_id}: {e}")
            return None

    return _parse_popup(popup_html, slug, booking_url_fallback)


def _parse_popup(
    popup_html: str,
    slug_fallback: str,
    booking_url_fallback: str | None,
) -> RawShowing | None:
    # Title
    tm = re.search(r'class="mb-ShortFilmTitle"[^>]*>(.*?)</h2>', popup_html, re.DOTALL)
    if not tm:
        return None
    title = html_lib.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
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
        logger.warning(
            f"Lewes Depot: cannot parse '{date_str} {time_str}' for '{slug_fallback}'"
        )
        return None

    # Booking URL — prefer the one embedded in the popup
    bm = re.search(r'href="(https://lewesdepot\.org/film/[^"]+/booknow/[^"]+)"', popup_html)
    booking_url = bm.group(1) if bm else booking_url_fallback

    # Screen name
    sm = re.search(r'class="mb-Screen">(.*?)</span>', popup_html)
    screen_name = sm.group(1).strip() if sm else None

    return RawShowing(
        title=title,
        start_time=start_time,
        booking_url=booking_url,
        screen_name=screen_name,
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
