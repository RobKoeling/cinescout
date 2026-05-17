"""Electric Cinema (Portobello / White City) scraper using Playwright."""

import asyncio
import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Response, async_playwright

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

# Programme page per location — the <ec-programme> web component renders here.
PROGRAMME_URLS: dict[str, str] = {
    "portobello": "https://www.electriccinema.co.uk/programme/list/portobello/",
    "white-city": "https://www.electriccinema.co.uk/programme/list/white-city/",
}

# The web component makes API calls as the page loads.  We intercept any JSON
# response whose URL contains one of these fragments to capture the schedule.
_API_URL_HINTS = ("programme", "screening", "film", "performance", "showing", "event")

# Maximum seconds to wait for the programme component to load.
_LOAD_TIMEOUT = 30_000


class ElectricCinemaScraper(BaseScraper):
    """
    Scraper for The Electric Cinema (Portobello Road and White City).

    The site uses an ``<ec-programme>`` custom web component that fetches
    schedule data via a private API as the page loads.  This scraper uses
    Playwright to intercept those network responses and parse the JSON
    directly.  If no suitable JSON is captured it falls back to parsing
    the rendered DOM for time links.

    Args:
        location: ``"portobello"`` (default) or ``"white-city"``.
    """

    def __init__(self, location: str = "portobello") -> None:
        self.location = location
        self._programme_url = PROGRAMME_URLS.get(location, PROGRAMME_URLS["portobello"])

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            showings = await self._scrape(date_from, date_to)
        except Exception as e:
            logger.error(f"Electric Cinema ({self.location}) scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Electric Cinema ({self.location}): Found {len(showings)} showings")
        return showings

    async def _scrape(self, date_from: date, date_to: date) -> list[RawShowing]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-GB",
                timezone_id="Europe/London",
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            # Intercept all JSON responses made during page load.
            captured: list[tuple[str, object]] = []

            async def on_response(response: Response) -> None:
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type:
                    return
                url = response.url
                if not any(h in url.lower() for h in _API_URL_HINTS):
                    return
                try:
                    data = await response.json()
                    if data:
                        captured.append((url, data))
                        logger.debug(
                            f"Electric Cinema: captured JSON from {url} "
                            f"({len(str(data))} chars)"
                        )
                except Exception:
                    pass

            page.on("response", on_response)

            await page.goto(self._programme_url, wait_until="domcontentloaded", timeout=_LOAD_TIMEOUT)
            # Give the web component time to fetch and render.
            try:
                await page.wait_for_load_state("networkidle", timeout=_LOAD_TIMEOUT)
            except Exception:
                pass  # networkidle can time out on busy pages; carry on
            await asyncio.sleep(2)

            html = await page.content()
            await browser.close()

        # Try to parse captured API responses first.
        if captured:
            logger.info(
                f"Electric Cinema ({self.location}): "
                f"captured {len(captured)} JSON response(s)"
            )
            for url, data in captured:
                showings = self._try_parse_api(data, date_from, date_to)
                if showings:
                    logger.info(
                        f"Electric Cinema ({self.location}): "
                        f"parsed {len(showings)} showings from {url}"
                    )
                    return showings
            logger.warning(
                f"Electric Cinema ({self.location}): captured JSON but couldn't parse showings"
            )

        # Fallback: parse the rendered DOM for time links.
        logger.info(f"Electric Cinema ({self.location}): falling back to DOM parsing")
        return self._parse_dom(html, date_from, date_to)

    # ------------------------------------------------------------------
    # API response parser (used when the web component's API is captured)
    # ------------------------------------------------------------------

    def _try_parse_api(self, data: object, date_from: date, date_to: date) -> list[RawShowing]:
        """
        Attempt to extract showings from an intercepted API response.

        The exact structure depends on whatever endpoint the ``<ec-programme>``
        web component calls; this method handles the most common patterns.
        """
        items: list[object] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Common wrappers: {"data": [...]} or {"results": [...]} or {"films": [...]}
            for key in ("data", "results", "films", "screenings", "performances", "events", "items"):
                val = data.get(key)
                if isinstance(val, list):
                    items = val
                    break

        if not items:
            return []

        showings: list[RawShowing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                parsed = self._parse_api_item(item, date_from, date_to)
                showings.extend(parsed)
            except Exception as e:
                logger.debug(f"Electric Cinema: failed to parse API item: {e}")
        return showings

    def _parse_api_item(
        self, item: dict[str, object], date_from: date, date_to: date
    ) -> list[RawShowing]:
        """Parse one item from the captured API response (best-effort)."""
        # Title — try common field names.
        title_raw: str = ""
        for key in ("title", "name", "film_title", "filmTitle", "film"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                title_raw = val.strip()
                break
            if isinstance(val, dict):
                for inner_key in ("title", "name"):
                    inner = val.get(inner_key)
                    if isinstance(inner, str) and inner.strip():
                        title_raw = inner.strip()
                        break
            if title_raw:
                break

        if not title_raw:
            return []
        title = self.normalise_title(title_raw)
        if not title:
            return []

        showings: list[RawShowing] = []

        # Showings might be nested in the item or the item IS a showing.
        for key in ("screenings", "showings", "performances", "times", "dates"):
            nested = item.get(key)
            if isinstance(nested, list):
                for s in nested:
                    if isinstance(s, dict):
                        showing = self._parse_showing_dict(title, s, date_from, date_to)
                        if showing:
                            showings.append(showing)
                return showings

        # Item itself might be a showing.
        showing = self._parse_showing_dict(title, item, date_from, date_to)
        if showing:
            showings.append(showing)
        return showings

    def _parse_showing_dict(
        self,
        title: str,
        d: dict[str, object],
        date_from: date,
        date_to: date,
    ) -> RawShowing | None:
        """Parse a dict that should contain a start datetime."""
        dt_str: str | None = None
        for key in ("start", "start_time", "startTime", "datetime", "date_time", "date", "time"):
            val = d.get(key)
            if isinstance(val, str) and val.strip():
                dt_str = val.strip()
                break

        if not dt_str:
            return None

        start_time = self._parse_datetime_str(dt_str)
        if start_time is None:
            return None

        showing_date = start_time.date()
        if not (date_from <= showing_date <= date_to):
            return None

        booking_url: str | None = None
        for key in ("url", "booking_url", "bookingUrl", "link", "href", "ticket_url"):
            val = d.get(key)
            if isinstance(val, str) and val.strip():
                booking_url = val.strip()
                break

        return RawShowing(title=title, start_time=start_time, booking_url=booking_url)

    def _parse_datetime_str(self, s: str) -> datetime | None:
        """Try several datetime formats and return an aware datetime, or None."""
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(s[:19], fmt)
                return dt.replace(tzinfo=LONDON_TZ)
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # DOM fallback parser
    # ------------------------------------------------------------------

    def _parse_dom(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        """
        Parse the Playwright-rendered HTML looking for time links near film titles.

        The ``<ec-programme>`` component renders film cards; we look for anchor
        tags whose visible text is a time (``HH:MM``) and walk up the DOM to
        find the nearest heading that is not a date.
        """
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        for link in soup.find_all("a", href=True):
            if not isinstance(link, Tag):
                continue
            text = link.get_text(strip=True)
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
            if not m:
                continue
            hour, minute = int(m.group(1)), int(m.group(2))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                continue

            title = self._find_dom_title(link)
            if not title:
                continue

            showing_date = self._find_dom_date(link, date_from, date_to)
            if showing_date is None:
                continue

            start_time = datetime(
                showing_date.year, showing_date.month, showing_date.day,
                hour, minute, tzinfo=LONDON_TZ,
            )
            booking_url = str(link.get("href") or "") or None

            showings.append(RawShowing(title=title, start_time=start_time, booking_url=booking_url))

        return showings

    def _find_dom_title(self, link: Tag) -> str | None:
        """Walk up the DOM to find the nearest heading that looks like a film title."""
        node: Tag | None = link.parent
        for _ in range(10):
            if not isinstance(node, Tag) or node.name in ("html", "body"):
                break
            for heading in node.find_all(["h1", "h2", "h3", "h4", "h5"]):
                if not isinstance(heading, Tag):
                    continue
                text = heading.get_text(strip=True)
                if not text or len(text) < 2:
                    continue
                # Skip date-like headings
                if re.match(
                    r"^(Today|Mon|Tue|Wed|Thu|Fri|Sat|Sun|"
                    r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d)",
                    text, re.IGNORECASE,
                ):
                    continue
                return self.normalise_title(text)
            node = node.parent
        return None

    def _find_dom_date(self, link: Tag, date_from: date, date_to: date) -> date | None:
        """Walk up the DOM to find the date context for this time link."""
        node: Tag | None = link.parent
        for _ in range(10):
            if not isinstance(node, Tag) or node.name in ("html", "body"):
                break
            for heading in node.find_all(["h1", "h2", "h3", "h4", "time"]):
                if not isinstance(heading, Tag):
                    continue
                # <time datetime="YYYY-MM-DD">
                dt_attr = heading.get("datetime")
                if isinstance(dt_attr, str) and re.match(r"\d{4}-\d{2}-\d{2}", dt_attr):
                    try:
                        d = date.fromisoformat(dt_attr[:10])
                        if date_from <= d <= date_to:
                            return d
                    except ValueError:
                        pass
                text = heading.get_text(strip=True)
                parsed = self._parse_date_text(text, date_from)
                if parsed and date_from <= parsed <= date_to:
                    return parsed
            node = node.parent
        # If we can't find a date, assume today if in range.
        today = date.today()
        if date_from <= today <= date_to:
            return today
        return None

    _MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    def _parse_date_text(self, text: str, ref_date: date) -> date | None:
        if text.lower() == "today":
            return date.today()
        m = re.search(r"(\d{1,2})\s+(\w{3,})", text)
        if not m:
            return None
        day = int(m.group(1))
        month = self._MONTH_MAP.get(m.group(2).lower()[:3])
        if not month:
            return None
        year = ref_date.year
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d < ref_date:
            try:
                d = date(year + 1, month, day)
            except ValueError:
                return None
        return d
