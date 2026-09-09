"""Phoenix Cinema scraper."""

import json
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

BASE_URL = "https://www.phoenixcinema.co.uk"
WHATS_ON_URL = f"{BASE_URL}/PhoenixCinemaLondon.dll/WhatsOn"

# Only scrape films and documentaries — exclude opera, ballet, theatre, etc.
_FILM_TYPES = {"Film", "Documentaries"}

# Performance flag → human-readable label
_PERF_FLAGS: dict[str, str] = {
    "CC": "Closed Captions",
    "AD": "Audio Description",
    "R": "Relaxed",
    "QA": "Q&A",
    "SU": "Subtitled",
}


class PhoenixScraper(BaseScraper):
    """
    Scraper for Phoenix Cinema (East Finchley).

    Uses the Savoy Systems platform. All film and performance data is embedded
    in the page HTML as ``var Events = {...}`` — same structure as Rio Cinema.
    The JSON includes release year which is used for film disambiguation.
    """

    WHATS_ON_URL = WHATS_ON_URL

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from Phoenix Cinema."""
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout, verify=False, follow_redirects=True
            ) as client:
                response = await client.get(self.WHATS_ON_URL)
                response.raise_for_status()
                showings = self._parse_html(response.text, date_from, date_to)
        except Exception as e:
            logger.error(f"Phoenix Cinema scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Phoenix Cinema: Found {len(showings)} showings")
        return showings

    def _parse_html(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        """Extract the embedded Events JSON and parse into RawShowings."""
        marker_match = re.search(r"var\s+Events\s*=\s*", html)
        if not marker_match:
            logger.warning("Phoenix Cinema: Could not find 'var Events' in page HTML")
            logger.debug(f"Phoenix Cinema: Page HTML snippet (first 2000 chars): {html[:2000]}")
            return []

        try:
            decoder = json.JSONDecoder()
            events_data, _ = decoder.raw_decode(html, marker_match.end())
        except json.JSONDecodeError as e:
            logger.error(f"Phoenix Cinema: Failed to parse Events JSON: {e}")
            return []

        films = events_data.get("Events", [])
        logger.debug(f"Phoenix Cinema: {len(films)} events found in embedded JSON")

        showings: list[RawShowing] = []
        for film in films:
            try:
                showings.extend(self._parse_film(film, date_from, date_to))
            except Exception as e:
                logger.warning(f"Phoenix Cinema: Failed to parse film entry: {e}")

        return showings

    def _parse_film(
        self, film: dict, date_from: date, date_to: date
    ) -> list[RawShowing]:
        # Skip non-film events (opera, ballet, theatre, etc.)
        if film.get("TypeDescription", "") not in _FILM_TYPES:
            return []

        title_raw = film.get("Title", "")
        if not title_raw:
            return []

        title = self.normalise_title(str(title_raw))
        if not title or len(title) < 2:
            return []

        # Use release year for disambiguation (e.g. Oldboy 2003 vs 2013)
        year: int | None = None
        year_str = film.get("Year", "")
        if year_str:
            try:
                year = int(str(year_str)[:4])
            except (ValueError, TypeError):
                pass

        showings: list[RawShowing] = []
        for perf in film.get("Performances", []):
            try:
                showing = self._parse_performance(title, year, perf, date_from, date_to)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(
                    f"Phoenix Cinema: Failed to parse performance for '{title}': {e}"
                )

        return showings

    def _parse_performance(
        self,
        title: str,
        year: int | None,
        perf: dict,
        date_from: date,
        date_to: date,
    ) -> RawShowing | None:
        start_date_str = perf.get("StartDate", "")  # "2026-03-27"
        start_time_str = perf.get("StartTime", "")  # "1500" (= 15:00)

        if not start_date_str or not start_time_str:
            return None

        try:
            perf_date = date.fromisoformat(start_date_str)
        except ValueError:
            return None

        if not (date_from <= perf_date <= date_to):
            return None

        # StartTime is a 4-char string like "1500", "0930", "2040"
        time_str = str(start_time_str).zfill(4)
        try:
            hour = int(time_str[:2])
            minute = int(time_str[2:])
        except (ValueError, IndexError):
            return None

        start_time = datetime(
            perf_date.year,
            perf_date.month,
            perf_date.day,
            hour,
            minute,
            tzinfo=LONDON_TZ,
        )

        # Build absolute booking URL from relative path
        perf_url = perf.get("URL", "")
        booking_url: str | None = None
        if perf_url:
            if perf_url.startswith("http"):
                booking_url = perf_url
            else:
                booking_url = f"{BASE_URL}/PhoenixCinemaLondon.dll/{perf_url}"

        screen_name = perf.get("AuditoriumName") or None
        format_tags = self._extract_format_tags(perf)

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            screen_name=str(screen_name) if screen_name else None,
            format_tags=format_tags,
            year=year,
        )

    def _extract_format_tags(self, perf: dict) -> str | None:
        """Build a comma-separated string of special screening tags."""
        tags = [label for flag, label in _PERF_FLAGS.items() if perf.get(flag) == "Y"]
        return ", ".join(tags) if tags else None
