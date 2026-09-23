"""Letterboxd public RSS client — no API key required or currently available.

Letterboxd does not have a confirmed, generally-accessible public API for
third-party apps to write diary entries. This client only reads a user's
public per-user diary RSS feed (https://letterboxd.com/<username>/rss/),
which needs no authentication.
"""

import html
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from xml.etree import ElementTree

import httpx

from cinescout.config import settings

logger = logging.getLogger(__name__)

# Letterboxd's RSS feed declares these namespaces on the <rss> root element.
_NAMESPACES = {
    "letterboxd": "https://letterboxd.com",
    "tmdb": "https://themoviedb.org",
}

# Each watchlist poster carries e.g. data-item-full-display-name="Clayface (2026)".
_WATCHLIST_ENTRY_RE = re.compile(r'data-item-full-display-name="([^"]+)"')
_WATCHLIST_YEAR_RE = re.compile(r"^(.*)\s\((\d{4})\)$")

# Safety cap on pagination — a real watchlist should never span this many pages.
_MAX_WATCHLIST_PAGES = 200


@dataclass
class LetterboxdEntry:
    """One diary entry parsed from a user's Letterboxd RSS feed."""

    film_title: str
    film_year: int | None
    watched_date: date
    rating: float | None
    rewatch: bool
    tmdb_id: int | None
    letterboxd_url: str | None


@dataclass
class WatchlistEntry:
    """One film parsed from a user's Letterboxd watchlist page."""

    title: str
    year: int | None


class LetterboxdClient:
    """Client for Letterboxd's public per-user diary RSS feed."""

    BASE_URL = "https://letterboxd.com"

    async def fetch_diary(self, username: str) -> list[LetterboxdEntry] | None:
        """
        Fetch and parse a user's public diary RSS feed.

        Returns None on any failure (private profile treated as an empty
        feed rather than a failure — see _parse_diary; this covers unknown
        username, network error, or unparseable feed). Returns [] for a
        valid feed with no diary entries.
        """
        url = f"{self.BASE_URL}/{username}/rss/"
        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.warning(f"Letterboxd user not found: {username}")
                    return None
                response.raise_for_status()
                xml_text = response.text
        except Exception as e:
            logger.error(f"Letterboxd RSS fetch error for {username!r}: {e}")
            return None

        try:
            return self._parse_diary(xml_text)
        except Exception as e:
            logger.error(f"Letterboxd RSS parse error for {username!r}: {e}")
            return None

    async def profile_exists(self, username: str) -> bool | None:
        """
        Check whether a Letterboxd profile's RSS feed is reachable.

        Returns True/False when confirmed, or None when the check itself
        failed (network error) — callers should treat None as "unknown,
        don't block" rather than a hard rejection.
        """
        url = f"{self.BASE_URL}/{username}/rss/"
        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return False
                response.raise_for_status()
                return True
        except Exception as e:
            logger.warning(f"Letterboxd profile check failed for {username!r}: {e}")
            return None

    async def fetch_watchlist(self, username: str) -> list[WatchlistEntry] | None:
        """
        Fetch and parse a user's public watchlist pages.

        Unlike the diary, Letterboxd exposes no RSS feed for watchlists — this
        walks the paginated HTML instead, extracting each entry's
        `data-item-full-display-name` ("Title (Year)") attribute rather than a
        TMDb id (not present on this page), so callers must go through
        FilmMatcher.match_or_create_film's title/year fuzzy matching rather
        than the diary import's tmdb_id-based lookup.

        Returns None on any failure to fetch the first page (unknown
        username, network error, private profile). Returns [] for a
        confirmed-empty watchlist.
        """
        entries: list[WatchlistEntry] = []
        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
                for page in range(1, _MAX_WATCHLIST_PAGES + 1):
                    url = (
                        f"{self.BASE_URL}/{username}/watchlist/"
                        if page == 1
                        else f"{self.BASE_URL}/{username}/watchlist/page/{page}/"
                    )
                    response = await client.get(url)
                    if response.status_code == 404:
                        if page == 1:
                            logger.warning(f"Letterboxd user not found: {username}")
                            return None
                        break
                    response.raise_for_status()

                    page_entries = self._parse_watchlist_page(response.text)
                    if not page_entries:
                        break
                    entries.extend(page_entries)
        except Exception as e:
            logger.error(f"Letterboxd watchlist fetch error for {username!r}: {e}")
            return None

        return entries

    def _parse_watchlist_page(self, html_text: str) -> list[WatchlistEntry]:
        entries = []
        for match in _WATCHLIST_ENTRY_RE.finditer(html_text):
            display_name = html.unescape(match.group(1))
            year_match = _WATCHLIST_YEAR_RE.match(display_name)
            if year_match:
                entries.append(WatchlistEntry(title=year_match.group(1), year=int(year_match.group(2))))
            else:
                entries.append(WatchlistEntry(title=display_name, year=None))
        return entries

    def _parse_diary(self, xml_text: str) -> list[LetterboxdEntry]:
        root = ElementTree.fromstring(xml_text)
        entries: list[LetterboxdEntry] = []

        for item in root.iterfind(".//item"):
            # Not every <item> is a diary entry (the same feed can include
            # reviews/lists) — presence of watchedDate is the discriminator.
            watched_date_el = item.find("letterboxd:watchedDate", _NAMESPACES)
            if watched_date_el is None or not watched_date_el.text:
                continue

            try:
                watched_date = datetime.strptime(watched_date_el.text.strip(), "%Y-%m-%d").date()
            except ValueError:
                logger.debug(f"Skipping entry with unparseable watchedDate: {watched_date_el.text}")
                continue

            title_el = item.find("letterboxd:filmTitle", _NAMESPACES)
            if title_el is None or not title_el.text:
                continue

            year_el = item.find("letterboxd:filmYear", _NAMESPACES)
            rating_el = item.find("letterboxd:memberRating", _NAMESPACES)
            rewatch_el = item.find("letterboxd:rewatch", _NAMESPACES)
            tmdb_el = item.find("tmdb:movieId", _NAMESPACES)
            link_el = item.find("link")

            rating = None
            if rating_el is not None and rating_el.text:
                try:
                    rating = float(rating_el.text.strip())
                except ValueError:
                    pass

            year = None
            if year_el is not None and year_el.text:
                try:
                    year = int(year_el.text.strip())
                except ValueError:
                    pass

            tmdb_id = None
            if tmdb_el is not None and tmdb_el.text:
                try:
                    tmdb_id = int(tmdb_el.text.strip())
                except ValueError:
                    pass

            entries.append(
                LetterboxdEntry(
                    film_title=title_el.text.strip(),
                    film_year=year,
                    watched_date=watched_date,
                    rating=rating,
                    rewatch=bool(
                        rewatch_el is not None and (rewatch_el.text or "").strip().lower() == "yes"
                    ),
                    tmdb_id=tmdb_id,
                    letterboxd_url=(
                        link_el.text.strip() if link_el is not None and link_el.text else None
                    ),
                )
            )

        return entries
