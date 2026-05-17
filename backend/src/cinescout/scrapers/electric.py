"""Electric Cinema (Portobello / White City) scraper."""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from cinescout.config import settings
from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")

DATA_URL = "https://www.electriccinema.co.uk/data/data.json"

# Cinema IDs in the data.json response
_CINEMA_IDS = {
    "portobello": "603",
    "white-city": "602",
}

_SCREENING_TYPES = {
    "BABY": "Babes in Arms",
    "KC": "Kids Club",
    "SE": "Electric Selects",
    "EA": "Subtitled",
}

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ElectricCinemaScraper(BaseScraper):
    """
    Scraper for The Electric Cinema (Portobello Road and White City).

    Fetches ``/data/data.json`` which contains all upcoming films and
    screenings in a single response.  Screenings are filtered to the
    requested cinema and date range.

    Args:
        location: ``"portobello"`` (default) or ``"white-city"``.
    """

    def __init__(self, location: str = "portobello") -> None:
        self.location = location
        self._cinema_id = _CINEMA_IDS.get(location, "603")

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.scrape_timeout,
                verify=False,
                follow_redirects=True,
                headers={"User-Agent": _UA},
            ) as client:
                r = await client.get(
                    DATA_URL,
                    params={"a": datetime.now(tz=LONDON_TZ).strftime("%c")},
                )
                r.raise_for_status()
                data = r.json()
                showings = self._parse(data, date_from, date_to)
        except Exception as e:
            logger.error(f"Electric Cinema ({self.location}) scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Electric Cinema ({self.location}): Found {len(showings)} showings")
        return showings

    def _parse(self, data: dict[str, object], date_from: date, date_to: date) -> list[RawShowing]:
        films: dict[str, object] = {}
        raw_films = data.get("films")
        if isinstance(raw_films, dict):
            films = raw_films

        screenings_raw = data.get("screenings")
        if not isinstance(screenings_raw, dict):
            return []

        showings: list[RawShowing] = []
        for screening in screenings_raw.values():
            if not isinstance(screening, dict):
                continue
            try:
                showing = self._parse_screening(screening, films, date_from, date_to)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.debug(f"Electric Cinema: failed to parse screening: {e}")
        return showings

    def _parse_screening(
        self,
        screening: dict[str, object],
        films: dict[str, object],
        date_from: date,
        date_to: date,
    ) -> RawShowing | None:
        if screening.get("cinema") != self._cinema_id:
            return None

        date_str = str(screening.get("d") or "")
        time_str = str(screening.get("t") or "")
        if not date_str or not time_str:
            return None

        try:
            screening_date = date.fromisoformat(date_str)
        except ValueError:
            return None

        if not (date_from <= screening_date <= date_to):
            return None

        film_id = str(screening.get("film") or "")
        film_data = films.get(film_id)
        if not isinstance(film_data, dict):
            return None

        title_raw = str(film_data.get("title") or "")
        title = self.normalise_title(title_raw)
        if not title:
            return None

        try:
            hour, minute = int(time_str[:2]), int(time_str[3:5])
        except (ValueError, IndexError):
            return None

        start_time = datetime(
            screening_date.year, screening_date.month, screening_date.day,
            hour, minute, tzinfo=LONDON_TZ,
        )

        link = screening.get("link")
        booking_url = str(link) if link and link is not False else None

        st = str(screening.get("st") or "")
        format_tags = _SCREENING_TYPES.get(st) if st else None

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            format_tags=format_tags,
        )
