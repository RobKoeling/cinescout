"""ArtHouse Crouch End scraper (WordPress + Savoy Systems)."""

import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
BASE_URL = "https://www.arthousecrouchend.co.uk"

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class ArtHouseCrouchEndScraper(BaseScraper):
    """
    Scraper for ArtHouse Crouch End.

    The site is WordPress-based. The homepage lists current films in
    ``.performance`` blocks, each linking to a programme detail page at
    ``/programme/?programme_id=XXXXX``. Each programme page contains a
    dated schedule: alternating ``div[id=dates]`` (date heading) and
    ``div.times`` (booking links with ``span.prog-times`` time text).
    """

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout, verify=False, follow_redirects=True
            ) as client:
                programme_ids = await self._fetch_programme_ids(client)
                if not programme_ids:
                    logger.warning("ArtHouse Crouch End: no programme IDs found on homepage")
                    return []

                showings: list[RawShowing] = []
                for pid, title in programme_ids.items():
                    try:
                        programme_showings = await self._fetch_programme(
                            client, pid, title, date_from, date_to
                        )
                        showings.extend(programme_showings)
                    except Exception as e:
                        logger.warning(
                            f"ArtHouse Crouch End: error fetching programme {pid}: {e}"
                        )

        except Exception as e:
            logger.error(f"ArtHouse Crouch End scraper error: {e}", exc_info=True)
            return []

        logger.info(f"ArtHouse Crouch End: Found {len(showings)} showings")
        return showings

    async def _fetch_programme_ids(
        self, client: httpx.AsyncClient
    ) -> dict[str, str]:
        """Return {programme_id: title} from the homepage film listings."""
        r = await client.get(BASE_URL + "/")
        if r.status_code != 200:
            logger.warning(f"ArtHouse Crouch End: homepage returned {r.status_code}")
            return {}

        soup = BeautifulSoup(r.text, "html.parser")
        programme_ids: dict[str, str] = {}

        for block in soup.find_all("div", class_="performance"):
            # Title is in .show-title a
            title_tag = block.find(class_="show-title")
            if not title_tag:
                continue
            title_a = title_tag.find("a")
            if not title_a:
                continue
            title = self.normalise_title(title_a.get_text(strip=True))
            if not title:
                continue

            # programme_id is in the href: /programme/?programme_id=XXXXX
            href = str(title_a.get("href") or "")
            m = re.search(r"programme_id=(\d+)", href)
            if not m:
                # Try thumb link
                thumb = block.find(class_="thumb")
                if thumb:
                    thumb_a = thumb.find("a")
                    if thumb_a:
                        m = re.search(r"programme_id=(\d+)", str(thumb_a.get("href") or ""))
            if m:
                programme_ids[m.group(1)] = title

        return programme_ids

    async def _fetch_programme(
        self,
        client: httpx.AsyncClient,
        programme_id: str,
        title: str,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """Fetch and parse all dated showings for one programme."""
        r = await client.get(f"{BASE_URL}/programme/?programme_id={programme_id}")
        if r.status_code != 200:
            logger.warning(
                f"ArtHouse Crouch End: programme {programme_id} returned {r.status_code}"
            )
            return []
        return self._parse_programme_page(r.text, title, date_from, date_to)

    def _parse_programme_page(
        self, html: str, title: str, date_from: date, date_to: date
    ) -> list[RawShowing]:
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find("div", class_="prog-background")
        if not container:
            return []

        showings: list[RawShowing] = []
        current_date: date | None = None

        # The structure is: div[id=dates] → div.times → div[id=dates] → div.times …
        for child in container.children:
            if not isinstance(child, Tag):
                continue

            if child.get("id") == "dates":
                current_date = self._parse_date_heading(child, date_from)

            elif child.name == "div" and "times" in (child.get("class") or []):
                if current_date is None:
                    continue
                for link in child.find_all("a"):
                    showing = self._parse_time_link(link, title, current_date)
                    if showing:
                        showings.append(showing)

        return showings

    def _parse_date_heading(self, div: Tag, date_from: date) -> date | None:
        """Parse a date heading div, returning the date or None if out of scope."""
        text = div.get_text(strip=True)

        if text.lower() == "today":
            return date.today()

        m = re.search(r"(\d{1,2})\s+(\w{3,})", text)
        if not m:
            return None
        day = int(m.group(1))
        month = _MONTH_MAP.get(m.group(2).lower()[:3])
        if not month:
            return None

        year = date_from.year
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d < date_from:
            try:
                d = date(year + 1, month, day)
            except ValueError:
                return None
        return d

    def _parse_time_link(self, link: Tag, title: str, showing_date: date) -> RawShowing | None:
        time_span = link.find("span", class_="prog-times")
        if not time_span:
            return None

        time_text = time_span.get_text(strip=True)
        m = re.match(r"(\d{1,2}):(\d{2})", time_text)
        if not m:
            return None

        start_time = datetime(
            showing_date.year, showing_date.month, showing_date.day,
            int(m.group(1)), int(m.group(2)),
            tzinfo=LONDON_TZ,
        )
        booking_url = link.get("href") or None

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=str(booking_url) if booking_url else None,
        )
