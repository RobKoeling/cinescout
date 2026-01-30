"""BFI Southbank scraper using Playwright for browser automation."""

import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")


class BFIScraper(BaseScraper):
    """
    Scraper for BFI Southbank.

    Uses Playwright for browser automation to bypass anti-bot protection.
    """

    BASE_URL = "https://whatson.bfi.org.uk"

    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch showings from BFI Southbank using Playwright."""
        showings: list[RawShowing] = []

        try:
            async with async_playwright() as p:
                # Launch browser with args to appear more like a real browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                    ]
                )
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                )
                page = await context.new_page()

                # Scrape each date
                current_date = date_from
                while current_date <= date_to:
                    date_showings = await self._scrape_date(page, current_date)
                    showings.extend(date_showings)
                    current_date = current_date + timedelta(days=1)

                await browser.close()

        except Exception as e:
            logger.error(f"BFI scraper error: {e}", exc_info=True)
            return []

        logger.info(f"BFI: Found {len(showings)} showings")
        return showings

    async def _scrape_date(
        self,
        page,
        showing_date: date,
    ) -> list[RawShowing]:
        """Scrape showings for a specific date."""
        date_str = showing_date.strftime("%Y-%m-%d")
        url = f"{self.BASE_URL}/Online/default.asp?BOparam::WScontent::loadArticle::permalink=whats-on&BOparam::WScontent::loadArticle::context_id=&date={date_str}"

        try:
            # Navigate to page
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Wait for Cloudflare challenge to complete (if present)
            # Look for the challenge completion or timeout after 15 seconds
            try:
                await page.wait_for_selector('body:not(:has-text("Just a moment"))', timeout=15000)
            except:
                logger.warning(f"Possible Cloudflare challenge for {date_str}")

            # Additional wait for dynamic content
            await page.wait_for_timeout(5000)

            # Get page content
            html = await page.content()

            # Check if we're still on Cloudflare challenge page
            if "Just a moment" in html or "challenge-platform" in html:
                logger.warning(f"Still on Cloudflare challenge page for {date_str}")
                return []

        except Exception as e:
            logger.warning(f"Failed to fetch BFI for {date_str}: {e}")
            return []

        return self._parse_html(html, showing_date)

    def _parse_html(self, html: str, showing_date: date) -> list[RawShowing]:
        """Parse BFI HTML to extract showings."""
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        # Debug: Save a sample of the HTML structure
        if showings == [] and logger.level <= logging.DEBUG:
            logger.debug(f"Sample HTML: {html[:2000]}")

        # Try multiple possible selectors for BFI's structure
        # The actual structure needs to be determined by inspecting the live site

        # Attempt 1: Look for common event/screening containers
        screening_items = (
            soup.find_all("div", class_=re.compile(r"event|screening|showing|film-item", re.I))
            or soup.find_all("article", class_=re.compile(r"event|screening|showing", re.I))
            or soup.find_all("li", class_=re.compile(r"event|screening|showing", re.I))
        )

        if not screening_items:
            # Attempt 2: Look for any structured listings
            screening_items = soup.find_all("div", class_=re.compile(r"item|card|listing", re.I))

        logger.debug(f"Found {len(screening_items)} potential screening items for {showing_date}")

        for item in screening_items:
            try:
                # Extract title - try multiple common patterns
                title_elem = (
                    item.find(["h1", "h2", "h3", "h4"], class_=re.compile(r"title|name|film", re.I))
                    or item.find("a", class_=re.compile(r"title|name|film", re.I))
                    or item.find(["h1", "h2", "h3", "h4"])
                )

                if not title_elem:
                    continue

                title = self.normalise_title(title_elem.get_text(strip=True))
                if not title or len(title) < 2:
                    continue

                # Extract time - look for time patterns
                time_elem = (
                    item.find(class_=re.compile(r"time|datetime|start", re.I))
                    or item.find("time")
                )

                if not time_elem:
                    # Try to find time in the text using regex
                    text = item.get_text()
                    time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', text)
                    if not time_match:
                        continue
                    time_str = time_match.group(0)
                else:
                    time_str = time_elem.get_text(strip=True)

                # Parse time (format: "18:30")
                try:
                    time_parts = re.match(r'(\d{1,2}):(\d{2})', time_str)
                    if not time_parts:
                        continue
                    hour, minute = int(time_parts.group(1)), int(time_parts.group(2))
                    start_time = datetime(
                        showing_date.year,
                        showing_date.month,
                        showing_date.day,
                        hour,
                        minute,
                        tzinfo=LONDON_TZ,
                    )
                except ValueError as e:
                    logger.warning(f"Invalid time format '{time_str}': {e}")
                    continue

                # Extract booking URL
                booking_link = (
                    item.find("a", class_=re.compile(r"book|buy|ticket", re.I))
                    or item.find("a", href=re.compile(r"book|buy|ticket", re.I))
                    or item.find("a")
                )
                booking_url = None
                if booking_link and booking_link.get("href"):
                    href = booking_link["href"]
                    booking_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                # Extract screen name
                screen_elem = item.find(class_=re.compile(r"screen|venue|auditorium", re.I))
                screen_name = screen_elem.get_text(strip=True) if screen_elem else None

                # Extract format/tags
                format_elem = item.find(class_=re.compile(r"format|tag|badge", re.I))
                format_tags = format_elem.get_text(strip=True) if format_elem else None

                showing = RawShowing(
                    title=title,
                    start_time=start_time,
                    booking_url=booking_url,
                    screen_name=screen_name,
                    format_tags=format_tags,
                )
                showings.append(showing)
                logger.debug(f"Parsed showing: {title} at {start_time}")

            except Exception as e:
                logger.warning(f"Failed to parse BFI screening item: {e}", exc_info=True)
                continue

        return showings
