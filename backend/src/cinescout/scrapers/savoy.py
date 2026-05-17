"""Shared base scraper for Savoy Systems cinemas (var Events JSON pattern)."""

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

# Type descriptions to skip (live theatre broadcasts etc.)
_SKIP_TYPE_DESCRIPTIONS = {"Theatre and Arts", "Opera", "Ballet", "Dance"}


class SavoySystemsScraper(BaseScraper):
    """
    Base scraper for cinemas using the Savoy Systems booking platform.

    The What's On page embeds all film/performance data as a JavaScript
    ``var Events = {"Events": [...]}`` assignment in the page HTML.

    Subclasses must set:
      - BASE_URL  : root URL of the cinema site
      - WHATS_ON_URL : full URL of the What's On page
      - CINEMA_NAME  : human-readable name for log messages
      - PERF_FLAGS   : mapping of JSON flag key → display label
    """

    BASE_URL: str
    WHATS_ON_URL: str
    CINEMA_NAME: str
    PERF_FLAGS: dict[str, str] = {}

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout, verify=False, follow_redirects=True
            ) as client:
                response = await client.get(self.WHATS_ON_URL)
                response.raise_for_status()
                showings = self._parse_html(response.text, date_from, date_to)
        except Exception as e:
            logger.error(f"{self.CINEMA_NAME} scraper error: {e}", exc_info=True)
            return []

        logger.info(f"{self.CINEMA_NAME}: Found {len(showings)} showings")
        return showings

    def _parse_html(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        marker = re.search(r"var\s+Events\s*=\s*", html)
        if not marker:
            logger.warning(f"{self.CINEMA_NAME}: Could not find 'var Events' in page HTML")
            return []
        try:
            events_data, _ = json.JSONDecoder().raw_decode(html, marker.end())
        except json.JSONDecodeError as e:
            logger.error(f"{self.CINEMA_NAME}: Failed to parse Events JSON: {e}")
            return []

        films = events_data.get("Events", [])
        showings: list[RawShowing] = []
        for film in films:
            try:
                showings.extend(self._parse_film(film, date_from, date_to))
            except Exception as e:
                logger.warning(f"{self.CINEMA_NAME}: Failed to parse film entry: {e}")
        return showings

    def _parse_film(
        self, film: dict[str, object], date_from: date, date_to: date
    ) -> list[RawShowing]:
        # Skip non-cinema event types
        type_desc = str(film.get("TypeDescription") or "")
        if type_desc in _SKIP_TYPE_DESCRIPTIONS:
            return []

        title_raw = str(film.get("Title") or "")
        if not title_raw:
            return []
        title = self.normalise_title(title_raw)
        if not title or len(title) < 2:
            return []

        year: int | None = None
        year_raw = film.get("Year")
        if year_raw:
            try:
                year = int(str(year_raw))
            except ValueError:
                pass

        showings: list[RawShowing] = []
        performances = film.get("Performances")
        if not isinstance(performances, list):
            return showings
        for perf in performances:
            try:
                showing = self._parse_performance(title, perf, date_from, date_to, year)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(
                    f"{self.CINEMA_NAME}: Failed to parse performance for '{title}': {e}"
                )
        return showings

    def _parse_performance(
        self,
        title: str,
        perf: dict[str, object],
        date_from: date,
        date_to: date,
        year: int | None,
    ) -> RawShowing | None:
        start_date_str = str(perf.get("StartDate") or "")
        start_time_str = str(perf.get("StartTime") or "")
        if not start_date_str or not start_time_str:
            return None

        try:
            perf_date = date.fromisoformat(start_date_str)
        except ValueError:
            return None

        if not (date_from <= perf_date <= date_to):
            return None

        time_str = start_time_str.zfill(4)
        try:
            hour, minute = int(time_str[:2]), int(time_str[2:])
        except (ValueError, IndexError):
            return None

        start_time = datetime(
            perf_date.year, perf_date.month, perf_date.day,
            hour, minute, tzinfo=LONDON_TZ,
        )

        perf_url = str(perf.get("URL") or "")
        booking_url: str | None = None
        if perf_url:
            if perf_url.startswith("http"):
                booking_url = perf_url
            else:
                booking_url = f"{self.BASE_URL}/{perf_url}"

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

    def _extract_format_tags(self, perf: dict[str, object]) -> str | None:
        tags = [
            label
            for flag, label in self.PERF_FLAGS.items()
            if perf.get(flag) == "Y"
        ]
        return ", ".join(tags) if tags else None
