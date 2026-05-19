"""Curzon Cinemas scraper using the ocapi/v1 Vista API with JWT auth."""

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

CURZON_BASE_URL = "https://www.curzon.com"
OCAPI_BASE = "https://digital-api.curzon.com/ocapi/v1"

# Vista site IDs for London venues (verified from /ocapi/v1/sites response)
# Map each site ID to the venue page slug used to fetch the auth token
VENUE_SLUGS: dict[str, str] = {
    "SOH1": "soho",
    "MAY1": "mayfair",
    "BLO1": "bloomsbury",
    "ALD1": "aldgate",
    "CAM1": "camden",
    "WIM01": "wimbledon",
    "HOX1": "hoxton",
    "VIC1": "victoria",
    "RIC1": "richmond",
    "KIN1": "kingston",
}

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class CurzonScraper(BaseScraper):
    """
    Scraper for Curzon Cinemas.

    Flow:
    1. Fetch a venue page and extract the JWT from ``window.initialData``.
    2. Call ``GET /ocapi/v1/sites/{venue_id}/films`` to seed an initial filmId→title map.
    3. For each date in the requested range call
       ``GET /ocapi/v1/showtimes/by-business-date/{date}?siteIds={venue_id}``.
       Each response includes ``relatedData.films`` with titles for that day's
       programme, which are merged into the film map automatically.
    4. Any remaining unresolved filmIds are looked up individually via
       ``GET /ocapi/v1/films/{filmId}``.
    """

    def __init__(self, venue_id: str = "SOH1") -> None:
        """
        Args:
            venue_id: Vista site ID (e.g. ``"SOH1"``, ``"MAY1"``, ``"WIM01"``).
        """
        self.venue_id = venue_id

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings for this Curzon venue."""
        try:
            auth_token = await self._get_auth_token()
            if not auth_token:
                logger.error(
                    f"Curzon ({self.venue_id}): Could not extract auth token from page"
                )
                return []

            showings = await self._fetch_showings(auth_token, date_from, date_to)

        except Exception as e:
            logger.error(f"Curzon ({self.venue_id}) scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Curzon ({self.venue_id}): Found {len(showings)} showings")
        return showings

    # ------------------------------------------------------------------
    # Auth token
    # ------------------------------------------------------------------

    async def _get_auth_token(self) -> str | None:
        """Return a Curzon JWT auth token.

        Tries, in order:
        1. ``CURZON_AUTH_TOKEN`` env var / settings — use when cloud IPs are blocked.
        2. Fetch live from the venue HTML page (works on residential/local IPs).
        """
        if settings.curzon_auth_token:
            logger.debug(f"Curzon ({self.venue_id}): using cached auth token from env")
            return settings.curzon_auth_token

        slug = VENUE_SLUGS.get(self.venue_id, "soho")
        url = f"{CURZON_BASE_URL}/venues/{slug}/"

        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout,
            verify=False,
            follow_redirects=True,
        ) as client:
            r = await client.get(
                url,
                headers={"User-Agent": _UA, "Accept": "text/html"},
            )
            r.raise_for_status()
            html = r.text

        m = re.search(r'"authToken"\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)

        logger.warning(
            f"Curzon ({self.venue_id}): authToken not found in page HTML ({url})"
        )
        return None

    # ------------------------------------------------------------------
    # Main fetch
    # ------------------------------------------------------------------

    async def _fetch_showings(
        self, auth_token: str, date_from: date, date_to: date
    ) -> list[RawShowing]:
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/json",
            "User-Agent": _UA,
        }

        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout, verify=False
        ) as client:
            film_map = await self._fetch_film_map(client, headers)
            if not film_map:
                logger.warning(
                    f"Curzon ({self.venue_id}): No films returned — venue may be closed or ID wrong"
                )
                # Don't abort; showtimes endpoint still works independently

            # year_map is built incrementally from relatedData.films in each day's response
            year_map: dict[str, int] = {}
            showings: list[RawShowing] = []
            current = date_from
            while current <= date_to:
                day_showings = await self._fetch_day(
                    client, headers, current, film_map, year_map
                )
                showings.extend(day_showings)
                current += timedelta(days=1)

            # Resolve any filmIds that weren't in the venue's /films list
            await self._resolve_unknown_film_ids(client, headers, film_map, showings)

        return showings

    async def _fetch_film_map(
        self, client: httpx.AsyncClient, headers: dict
    ) -> dict[str, str]:
        """Return {filmId: normalised_title} for the current programme at this venue."""
        r = await client.get(
            f"{OCAPI_BASE}/sites/{self.venue_id}/films", headers=headers
        )
        if r.status_code != 200:
            logger.warning(
                f"Curzon ({self.venue_id}): /films returned {r.status_code}"
            )
            return {}

        films = r.json().get("films", [])
        film_map: dict[str, str] = {}
        for film in films:
            film_id = film.get("id")
            title_raw = film.get("title", {}).get("text", "")
            if film_id and title_raw:
                film_map[film_id] = self.normalise_title(title_raw)
        return film_map

    async def _fetch_day(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        day: date,
        film_map: dict[str, str],
        year_map: dict[str, int],
    ) -> list[RawShowing]:
        r = await client.get(
            f"{OCAPI_BASE}/showtimes/by-business-date/{day.isoformat()}",
            headers=headers,
            params={"siteIds": self.venue_id},
        )

        if r.status_code != 200:
            logger.warning(
                f"Curzon ({self.venue_id}): showtimes/{day} returned {r.status_code}"
            )
            return []

        data = r.json()
        showtimes = data.get("showtimes", [])

        # The response includes relatedData.films with titles and release dates for
        # all films in this day's programme — merge them into the shared maps.
        for film in data.get("relatedData", {}).get("films", []):
            film_id = film.get("id")
            title_raw = film.get("title", {}).get("text", "")
            if film_id and title_raw and film_id not in film_map:
                film_map[film_id] = self.normalise_title(title_raw)
            release_date = film.get("releaseDate", "")
            if film_id and release_date and film_id not in year_map:
                try:
                    year_map[film_id] = int(release_date[:4])
                except (ValueError, IndexError):
                    pass

        showings: list[RawShowing] = []

        for st in showtimes:
            try:
                showing = self._parse_showtime(st, film_map, year_map, day)
                if showing:
                    showings.append(showing)
            except Exception as e:
                logger.warning(
                    f"Curzon ({self.venue_id}): Failed to parse showtime {st.get('id')}: {e}"
                )

        return showings

    async def _resolve_unknown_film_ids(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        film_map: dict[str, str],
        showings: list[RawShowing],
    ) -> None:
        """Look up titles for filmIds that were not in the /sites/{venue}/films list.

        The /sites/{venue}/films endpoint only returns a subset of films (typically
        curated/featured). Showings may reference filmIds not in that list; for those
        we fall back to using the filmId as the title. This method fetches the real
        title from /films/{filmId} and patches the showing in place.
        """
        # Curzon filmIds look like "HO00006736" — collect any showing whose title is
        # still the raw filmId (i.e. was not resolved via film_map).
        unknown_ids: set[str] = {
            s.title for s in showings if re.fullmatch(r"[A-Z]{2}\d+", s.title)
        }
        if not unknown_ids:
            return

        logger.debug(
            f"Curzon ({self.venue_id}): resolving {len(unknown_ids)} unknown filmId(s)"
        )
        for film_id in unknown_ids:
            try:
                r = await client.get(
                    f"{OCAPI_BASE}/films/{film_id}", headers=headers
                )
                if r.status_code != 200:
                    continue
                title_raw = r.json().get("film", {}).get("title", {}).get("text", "")
                if title_raw:
                    film_map[film_id] = self.normalise_title(title_raw)
            except Exception as e:
                logger.warning(
                    f"Curzon ({self.venue_id}): failed to resolve filmId {film_id}: {e}"
                )

        # Patch any showings that still have a raw filmId as their title
        for showing in showings:
            if showing.title in film_map:
                showing.title = film_map[showing.title]

    def _parse_showtime(
        self,
        st: dict,
        film_map: dict[str, str],
        year_map: dict[str, int],
        day: date,
    ) -> RawShowing | None:
        film_id = st.get("filmId", "")
        title = film_map.get(film_id, "")
        if not title:
            # Fall back: use filmId as a crude placeholder so the showing isn't lost
            # (film matcher will likely fail, but at least we track it)
            if not film_id:
                return None
            title = film_id  # will be overridden by FilmMatcher if possible

        starts_at = st.get("schedule", {}).get("startsAt", "")
        if not starts_at:
            return None

        try:
            start_time = datetime.fromisoformat(starts_at)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=LONDON_TZ)
        except ValueError:
            return None

        # Sanity-check: showing must be on the requested day
        if start_time.date() != day:
            return None

        showing_id = st.get("id", "")
        booking_url = (
            f"{CURZON_BASE_URL}/ticketing/seats/{showing_id}/"
            if showing_id
            else None
        )

        return RawShowing(
            title=title,
            start_time=start_time,
            booking_url=booking_url,
            year=year_map.get(film_id),
        )
