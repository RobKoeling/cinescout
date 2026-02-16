"""Film matching service with fuzzy matching and TMDb integration."""

import logging
import re
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.models.film import Film
from cinescout.models.film_alias import FilmAlias
from cinescout.services.tmdb_client import TMDbClient
from cinescout.utils.text import normalise_title, slugify

logger = logging.getLogger(__name__)


class FilmMatcher:
    """
    Service for matching cinema film titles to canonical film records.

    Uses a multi-stage matching process:
    1. Check film_aliases for exact match
    2. Fuzzy match against existing films
    3. Search TMDb API if no local match
    4. Create new film from TMDb or placeholder
    5. Store alias for future lookups
    """

    FUZZY_THRESHOLD = 85  # Minimum similarity score for fuzzy matching

    def __init__(self, db: AsyncSession, tmdb_client: TMDbClient | None = None) -> None:
        """
        Initialize film matcher.

        Args:
            db: Database session
            tmdb_client: TMDb client (creates default if not provided)
        """
        self.db = db
        self.tmdb_client = tmdb_client or TMDbClient()

    async def match_or_create_film(self, raw_title: str) -> Film:
        """
        Match a raw cinema title to an existing film or create a new one.

        Args:
            raw_title: Film title as it appears on cinema website

        Returns:
            Matched or newly created Film object
        """
        # Normalize the title
        normalized_title = normalise_title(raw_title)
        logger.info(f"Matching film: '{raw_title}' -> '{normalized_title}'")

        # Stage 1: Check film_aliases for exact match
        film = await self._check_alias(normalized_title)
        if film:
            logger.info(f"Found via alias: {film.title}")
            return film

        # Stage 2: Fuzzy match against existing films
        film = await self._fuzzy_match(normalized_title)
        if film:
            logger.info(f"Found via fuzzy match: {film.title}")
            await self._store_alias(normalized_title, film.id)
            return film

        # Stage 3 & 4: Search TMDb and create new film
        film = await self._create_from_tmdb(normalized_title)
        if film:
            logger.info(f"Created from TMDb: {film.title}")
            await self._store_alias(normalized_title, film.id)
            return film

        # Fallback: Create placeholder film
        film = await self._create_placeholder(normalized_title)
        logger.info(f"Created placeholder: {film.title}")
        await self._store_alias(normalized_title, film.id)
        return film

    async def _check_alias(self, normalized_title: str) -> Film | None:
        """Check if normalized title exists in film_aliases table."""
        query = (
            select(Film)
            .join(FilmAlias)
            .where(FilmAlias.normalized_title == normalized_title)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _fuzzy_match(self, normalized_title: str) -> Film | None:
        """Fuzzy match normalized title against existing films."""
        # Get all existing films
        query = select(Film)
        result = await self.db.execute(query)
        films = result.scalars().all()

        if not films:
            return None

        # Find best match using rapidfuzz
        best_score = 0.0
        best_film = None

        for film in films:
            score = fuzz.ratio(normalized_title.lower(), film.title.lower())
            if score > best_score:
                best_score = score
                best_film = film

        # Return match if above threshold
        if best_score >= self.FUZZY_THRESHOLD and best_film:
            logger.info(f"Fuzzy match: {best_score:.1f}% - '{normalized_title}' -> '{best_film.title}'")
            return best_film

        return None

    async def _create_from_tmdb(self, normalized_title: str) -> Film | None:
        """Create film from TMDb data."""
        # Extract year from title if present
        year_match = re.search(r"\((\d{4})\)", normalized_title)
        year = int(year_match.group(1)) if year_match else None

        # Search TMDb
        search_result = await self.tmdb_client.search_film(normalized_title, year)
        if not search_result:
            return None

        tmdb_id = search_result["id"]

        # Get detailed info including credits
        details = await self.tmdb_client.get_film_details(tmdb_id)
        if not details:
            return None

        # Extract metadata
        title = details.get("title", normalized_title)
        year = self._extract_year(details.get("release_date"))
        directors = self.tmdb_client.extract_directors(details.get("credits", {}))
        countries = self.tmdb_client.extract_countries(details)
        cast = self.tmdb_client.extract_cast(details.get("credits", {}))
        overview = details.get("overview")
        poster_path = details.get("poster_path")
        runtime = details.get("runtime")

        # Create film ID from title and year
        film_id = self._generate_film_id(title, year)

        # Create film object
        film = Film(
            id=film_id,
            title=title,
            year=year,
            tmdb_id=tmdb_id,
            directors=directors if directors else None,
            countries=countries if countries else None,
            cast=cast if cast else None,
            overview=overview,
            poster_path=poster_path,
            runtime=runtime,
        )

        try:
            self.db.add(film)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            # Another cinema in this run already created the same film; fetch it.
            existing = await self.db.get(Film, film_id)
            if existing:
                logger.debug(f"Film {film_id!r} already exists, reusing.")
                return existing
            raise

        return film

    async def _create_placeholder(self, normalized_title: str) -> Film:
        """Create a placeholder film when no TMDb match is found."""
        # Extract year if present in title
        year_match = re.search(r"\((\d{4})\)", normalized_title)
        year = int(year_match.group(1)) if year_match else None

        # Remove year from title for display
        display_title = re.sub(r"\s*\(\d{4}\)\s*$", "", normalized_title)

        # Generate film ID
        film_id = self._generate_film_id(display_title, year)

        film = Film(
            id=film_id,
            title=display_title,
            year=year,
            tmdb_id=None,
            directors=None,
            countries=None,
            overview=None,
            poster_path=None,
            runtime=None,
        )

        try:
            self.db.add(film)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            existing = await self.db.get(Film, film_id)
            if existing:
                logger.debug(f"Film {film_id!r} already exists, reusing.")
                return existing
            raise

        return film

    async def _store_alias(self, normalized_title: str, film_id: str) -> None:
        """Store a film alias for faster future lookups."""
        # Check if alias already exists
        query = select(FilmAlias).where(FilmAlias.normalized_title == normalized_title)
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            return  # Alias already exists

        alias = FilmAlias(
            normalized_title=normalized_title,
            film_id=film_id,
        )
        self.db.add(alias)
        await self.db.flush()

    def _extract_year(self, release_date: str | None) -> int | None:
        """Extract year from TMDb release date string."""
        if not release_date:
            return None
        try:
            return int(release_date[:4])
        except (ValueError, IndexError):
            return None

    def _generate_film_id(self, title: str, year: int | None) -> str:
        """Generate a film ID from title and year."""
        slug = slugify(title)
        if year:
            return f"{slug}-{year}"
        return slug
