"""Cine Lumière (Institut Français du Royaume-Uni) scraper."""

import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
WHATS_ON_URL = "https://www.institut-francais.org.uk/cine-lumiere/whats-on/"
BOOKING_DOMAIN = "cinelumiere.savoysystems.co.uk"

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

_DATE_PREFIXES = re.compile(
    r"^(Today|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Mon|Tue|Wed|Thu|Fri|Sat|Sun|"
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December|\d)",
    re.IGNORECASE,
)


class CineLumiereScraper(BaseScraper):
    """
    Scraper for Cine Lumière at Institut Français du Royaume-Uni, South Kensington.

    Fetches ``/cine-lumiere/whats-on/?date=YYYY-MM-DD`` once per day in the
    requested range.  The page is server-side rendered WordPress: booking anchor
    tags point to ``cinelumiere.savoysystems.co.uk`` and contain a ``HH:MM``
    time as their visible text.  The film title lives in the nearest ancestor
    heading that does not look like a date header.
    """

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout,
                verify=False,
                follow_redirects=True,
                headers={"User-Agent": _UA},
            ) as client:
                showings: list[RawShowing] = []
                current = date_from
                while current <= date_to:
                    try:
                        day_showings = await self._fetch_day(client, current)
                        showings.extend(day_showings)
                    except Exception as e:
                        logger.warning(f"Cine Lumière: error fetching {current}: {e}")
                    current += timedelta(days=1)
        except Exception as e:
            logger.error(f"Cine Lumière scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Cine Lumière: Found {len(showings)} showings")
        return showings

    async def _fetch_day(self, client: httpx.AsyncClient, day: date) -> list[RawShowing]:
        r = await client.get(WHATS_ON_URL, params={"date": day.isoformat()})
        if r.status_code != 200:
            logger.warning(f"Cine Lumière: {day} returned {r.status_code}")
            return []
        return self._parse_day(r.text, day)

    def _parse_day(self, html: str, day: date) -> list[RawShowing]:
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []

        for link in soup.find_all("a", href=re.compile(re.escape(BOOKING_DOMAIN))):
            if not isinstance(link, Tag):
                continue
            showing = self._parse_booking_link(link, day)
            if showing:
                showings.append(showing)

        return showings

    def _parse_booking_link(self, link: Tag, day: date) -> RawShowing | None:
        time_text = link.get_text(strip=True)
        m = re.match(r"(\d{1,2})[:\.](\d{2})", time_text)
        if not m:
            return None
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        title = self._find_title(link)
        if not title:
            logger.debug(f"Cine Lumière: could not find title for booking link {link.get('href')}")
            return None

        start_time = datetime(day.year, day.month, day.day, hour, minute, tzinfo=LONDON_TZ)
        booking_url = str(link.get("href") or "") or None

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
        )

    def _find_title(self, link: Tag) -> str | None:
        """Find the nearest film-title heading that precedes this booking link."""
        # Pass a list so find_previous returns the single closest preceding element
        # of any heading level — the film h3 is nearer than the page-title h1.
        heading = link.find_previous(["h1", "h2", "h3", "h4", "h5"])
        if not isinstance(heading, Tag):
            return None
        text = heading.get_text(strip=True)
        if not text or len(text) < 2 or _DATE_PREFIXES.match(text):
            return None
        return self.normalise_title(text)
