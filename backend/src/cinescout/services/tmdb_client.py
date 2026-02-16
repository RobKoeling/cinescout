"""TMDb API client for fetching film metadata."""

import logging
from typing import Any

import httpx

from cinescout.config import settings

logger = logging.getLogger(__name__)


class TMDbClient:
    """Client for The Movie Database (TMDb) API."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize TMDb client.

        Args:
            api_key: TMDb API key (uses settings if not provided)
        """
        self.api_key = api_key or settings.tmdb_api_key
        if not self.api_key:
            logger.warning("TMDb API key not configured")

    async def search_film(self, title: str, year: int | None = None) -> dict[str, Any] | None:
        """
        Search for a film by title.

        Args:
            title: Film title
            year: Release year (optional, helps narrow results)

        Returns:
            First matching film result or None if not found
        """
        if not self.api_key:
            logger.warning("Cannot search TMDb without API key")
            return None

        params: dict[str, Any] = {
            "api_key": self.api_key,
            "query": title,
            "language": "en-GB",
        }
        if year:
            params["year"] = year

        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
                response = await client.get(f"{self.BASE_URL}/search/movie", params=params)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    logger.info(f"No TMDb results for: {title}")
                    return None

                # Return the first result
                return results[0]

        except Exception as e:
            logger.error(f"TMDb search error for '{title}': {e}")
            return None

    async def get_film_details(self, tmdb_id: int) -> dict[str, Any] | None:
        """
        Get detailed film information including credits.

        Args:
            tmdb_id: TMDb film ID

        Returns:
            Film details including credits or None if error
        """
        if not self.api_key:
            logger.warning("Cannot fetch TMDb details without API key")
            return None

        params = {
            "api_key": self.api_key,
            "language": "en-GB",
            "append_to_response": "credits",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.scrape_timeout, verify=False) as client:
                response = await client.get(
                    f"{self.BASE_URL}/movie/{tmdb_id}",
                    params=params,
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"TMDb details error for ID {tmdb_id}: {e}")
            return None

    def extract_directors(self, credits: dict[str, Any]) -> list[str]:
        """
        Extract director names from TMDb credits.

        Args:
            credits: TMDb credits data

        Returns:
            List of director names
        """
        crew = credits.get("crew", [])
        directors = [
            person["name"] for person in crew if person.get("job") == "Director"
        ]
        return directors

    def extract_countries(self, film_data: dict[str, Any]) -> list[str]:
        """
        Extract country names from TMDb film data.

        Args:
            film_data: TMDb film details

        Returns:
            List of country names
        """
        countries = film_data.get("production_countries", [])
        return [country["name"] for country in countries]

    def extract_cast(self, credits: dict[str, Any], n: int = 3) -> list[str]:
        """
        Extract top-billed cast member names from TMDb credits.

        Args:
            credits: TMDb credits data
            n: Maximum number of cast members to return

        Returns:
            List of actor names (up to n)
        """
        cast = credits.get("cast", [])
        return [person["name"] for person in cast[:n] if person.get("name")]
