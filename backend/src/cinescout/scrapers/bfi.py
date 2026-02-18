"""BFI Southbank scraper using Playwright with stealth to bypass Cloudflare."""

import asyncio
import json
import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

FILMS_INDEX_URL = (
    "https://whatson.bfi.org.uk/Online/default.asp"
    "?BOparam::WScontent::loadArticle::permalink=filmsindex"
)

BASE_URL = "https://whatson.bfi.org.uk/Online"

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# Indicators that we're on a Cloudflare challenge page (not the real site).
# Note: "challenge-platform" appears as a script path on real pages too, so we
# check for the actual challenge page title and interstitial markers instead.
CLOUDFLARE_INDICATORS = (
    "<title>Just a moment</title>",
    "cf-challenge-running",
    "cf_chl_opt",
)

MAX_RETRIES = 3
BACKOFF_BASE = 5  # seconds


class BFIScraper(BaseScraper):
    """Scraper for BFI Southbank. Uses playwright-stealth to bypass Cloudflare.

    Strategy: navigate to the filmsindex calendar page (one Cloudflare challenge),
    then click each date in the requested range to load search results. Each
    result page contains `.result-box-item` elements with structured film data.
    """

    BASE_URL = "https://whatson.bfi.org.uk"

    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch showings from BFI Southbank by clicking dates on the calendar."""
        showings: list[RawShowing] = []

        try:
            showings = await self._scrape_with_retries(date_from, date_to)
        except Exception as e:
            logger.error(f"BFI scraper error: {e}", exc_info=True)

        logger.info(f"BFI: Found {len(showings)} showings")
        return showings

    async def _scrape_with_retries(
        self, date_from: date, date_to: date
    ) -> list[RawShowing]:
        """Launch stealth browser and scrape, retrying on Cloudflare blocks."""
        stealth = Stealth()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with stealth.use_async(async_playwright()) as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        locale="en-GB",
                        timezone_id="Europe/London",
                    )
                    page = await context.new_page()

                    # Navigate to filmsindex and wait for Cloudflare
                    html = await self._navigate_and_wait(page)
                    if not html:
                        logger.warning(
                            f"BFI: Cloudflare blocked attempt {attempt}/{MAX_RETRIES}"
                        )
                        await browser.close()
                        if attempt < MAX_RETRIES:
                            delay = BACKOFF_BASE * (2 ** (attempt - 1))
                            logger.info(f"BFI: Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                        continue

                    logger.info(
                        f"BFI: Loaded filmsindex on attempt {attempt} "
                        f"({len(html)} chars)"
                    )

                    # Click each date and collect results
                    showings = await self._scrape_dates(page, date_from, date_to)
                    await browser.close()
                    return showings

            except Exception as e:
                logger.warning(
                    f"BFI: Error on attempt {attempt}/{MAX_RETRIES}: {e}",
                    exc_info=True,
                )
                if attempt < MAX_RETRIES:
                    delay = BACKOFF_BASE * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        logger.warning("BFI: Failed to fetch page after all retries")
        return []

    async def _navigate_and_wait(self, page: Page) -> str | None:
        """Navigate to the filmsindex URL and wait for Cloudflare to clear.

        Returns the page HTML if Cloudflare cleared, or None if still blocked.
        """
        await page.goto(FILMS_INDEX_URL, wait_until="domcontentloaded", timeout=60000)

        # Poll for up to 15 seconds checking if Cloudflare challenge has cleared
        for _ in range(15):
            await asyncio.sleep(1)
            html = await page.content()
            if not any(indicator in html for indicator in CLOUDFLARE_INDICATORS):
                return html

        return None

    async def _scrape_dates(
        self, page: Page, date_from: date, date_to: date
    ) -> list[RawShowing]:
        """Click each available date button and parse the results page."""
        showings: list[RawShowing] = []

        # Determine target day numbers from the calendar
        target_days = await self._get_target_days(page, date_from, date_to)
        logger.debug(f"BFI: {len(target_days)} date buttons in range")

        for day_num in target_days:
            try:
                # Re-find the button fresh each iteration (DOM resets after back-nav)
                btn = await self._find_day_button(page, day_num)
                if not btn:
                    logger.warning(f"BFI: Could not find button for day {day_num}")
                    continue

                logger.debug(f"BFI: Clicking day {day_num}")
                async with page.expect_navigation(timeout=30000):
                    await btn.click()

                await asyncio.sleep(2)
                html = await page.content()
                day_showings = self._parse_results_html(html)
                showings.extend(day_showings)
                logger.debug(f"BFI: Day {day_num} → {len(day_showings)} showings")

                # Navigate back to the calendar for the next date
                await page.go_back(wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"BFI: Error scraping day {day_num}: {e}")
                # Try to recover by navigating back to filmsindex
                try:
                    await page.goto(
                        FILMS_INDEX_URL, wait_until="domcontentloaded", timeout=30000
                    )
                    await asyncio.sleep(2)
                except Exception:
                    break

        return showings

    async def _get_target_days(
        self, page: Page, date_from: date, date_to: date
    ) -> list[int]:
        """Read the calendar and return day numbers that fall in the date range."""
        buttons = await page.query_selector_all(".calendar-date-button")
        if not buttons:
            logger.warning("BFI: No calendar date buttons found")
            return []

        # Determine the calendar's displayed month/year
        month_display = await page.query_selector(".calendar-month-display")
        cal_month, cal_year = None, None
        if month_display:
            month_text = (await month_display.text_content() or "").strip()
            match = re.match(r"(\w+)\s+(\d{4})", month_text)
            if match:
                cal_month = MONTH_MAP.get(match.group(1).lower())
                cal_year = int(match.group(2))
                logger.debug(f"BFI: Calendar shows {match.group(0)}")

        if not cal_month or not cal_year:
            return []

        target_days: list[int] = []
        for btn in buttons:
            day_text = (await btn.text_content() or "").strip()
            if not day_text.isdigit():
                continue
            day_num = int(day_text)
            try:
                btn_date = date(cal_year, cal_month, day_num)
            except ValueError:
                continue
            if date_from <= btn_date <= date_to:
                target_days.append(day_num)

        return target_days

    async def _find_day_button(self, page: Page, day_num: int) -> object | None:
        """Find a fresh calendar button handle for the given day number."""
        buttons = await page.query_selector_all(".calendar-date-button")
        for btn in buttons:
            text = (await btn.text_content() or "").strip()
            if text == str(day_num):
                return btn
        return None

    def _parse_results_html(self, html: str) -> list[RawShowing]:
        """Parse a BFI search results page.

        Each showing is a `.result-box-item` div containing:
        - `.item-name a.more-info` — title
        - `.start-date` — "Sunday 15 February 2026 18:00"
        - `.item-venue` — screen name
        - `.item-link.good` — has a Buy button (available)
        - `.item-link.soldout` — sold out
        """
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        # Build format lookup from the JS data embedded in the page
        format_lookup = self._extract_format_lookup(html)

        items = soup.find_all("div", class_="result-box-item")
        if not items:
            logger.debug("BFI: No .result-box-item elements on results page")
            return []

        for item in items:
            try:
                showing = self._parse_result_item(item, format_lookup)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(f"BFI: Failed to parse result item: {e}", exc_info=True)

        return showings

    def _extract_format_lookup(self, html: str) -> dict[tuple[str, str], str]:
        """Extract format tags from the articleContext.searchResults JS data.

        The page embeds a JS object with searchResults: an array of arrays.
        Index 5 = title (description), index 7 = full date string, index 17 = keywords
        (comma-separated, e.g. "35mm,Kathryn Bigelow").

        Returns a dict mapping (title, date_string) → format_tag.
        """
        m = re.search(r'"?searchResults"?\s*:\s*(\[)', html)
        if not m:
            return {}

        start = m.start(1)
        depth = 0
        end = start
        for i, ch in enumerate(html[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        try:
            results = json.loads(html[start:end])
        except (json.JSONDecodeError, ValueError):
            logger.debug("BFI: Could not parse searchResults JS data")
            return {}

        known_formats = {'35mm', '70mm', '4k', 'imax'}
        lookup: dict[tuple[str, str], str] = {}
        for record in results:
            if not isinstance(record, list) or len(record) <= 17:
                continue
            title = str(record[5])
            date_str = str(record[7])
            keywords_str = str(record[17])
            tags = [t.strip().lower() for t in keywords_str.split(',')]
            format_tag = next((t for t in tags if t in known_formats), None)
            if format_tag:
                lookup[(title, date_str)] = format_tag

        logger.debug(f"BFI: format lookup has {len(lookup)} 35mm/format entries")
        return lookup

    def _parse_result_item(
        self,
        item: Tag,
        format_lookup: dict[tuple[str, str], str] | None = None,
    ) -> RawShowing | None:
        """Parse a single .result-box-item into a RawShowing."""
        # Title
        name_link = item.select_one(".item-name a.more-info")
        if not name_link:
            return None

        title_raw = name_link.get_text(strip=True)
        title = self.normalise_title(title_raw)
        if not title or len(title) < 2:
            return None

        # Date and time from .start-date span
        # Format: "Sunday 15 February 2026 18:00"
        start_date_elem = item.select_one(".start-date")
        if not start_date_elem:
            return None

        start_text = start_date_elem.get_text(strip=True)
        start_time = self._parse_start_date(start_text)
        if not start_time:
            logger.warning(f"BFI: Could not parse date '{start_text}' for '{title}'")
            return None

        # Booking URL from the more-info link
        href = name_link.get("href", "")
        booking_url = href if href.startswith("http") else f"{BASE_URL}/{href}"

        # Screen name
        venue_elem = item.select_one(".item-venue")
        screen_name = venue_elem.get_text(strip=True) if venue_elem else None

        # Format tags from JS data lookup (keyed by raw title + full date string)
        format_tags = format_lookup.get((title_raw, start_text)) if format_lookup else None

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            screen_name=screen_name,
            format_tags=format_tags,
        )

    def _parse_start_date(self, text: str) -> datetime | None:
        """Parse a BFI start date string like 'Sunday 15 February 2026 18:00'."""
        match = re.search(
            r"(\d{1,2})\s+(\w+)\s+(\d{4})\s+(\d{1,2}):(\d{2})",
            text,
        )
        if not match:
            return None

        day = int(match.group(1))
        month = MONTH_MAP.get(match.group(2).lower())
        if not month:
            return None

        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))

        try:
            return datetime(year, month, day, hour, minute, tzinfo=LONDON_TZ)
        except ValueError:
            return None
