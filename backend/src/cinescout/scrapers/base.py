"""Base scraper interface for all cinema scrapers."""

from abc import ABC, abstractmethod
from datetime import date

from cinescout.scrapers.models import RawShowing
from cinescout.utils.text import normalise_title


class BaseScraper(ABC):
    """
    Abstract base class for all cinema scrapers.

    All scrapers must implement the get_showings method.
    Optionally, they can implement get_availability for real-time seat checks.
    """

    @abstractmethod
    async def get_showings(
        self,
        date_from: date,
        date_to: date,
    ) -> list[RawShowing]:
        """
        Fetch showings for the given date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of raw showings

        Raises:
            Should NOT raise exceptions. Return empty list on errors and log warnings.
        """
        pass

    async def get_availability(self, booking_url: str) -> dict | None:
        """
        Check real-time seat availability for a specific showing.

        Optional method for cinemas that support availability checks.

        Args:
            booking_url: URL to the booking page

        Returns:
            Dictionary with availability info (seats_available, total_seats, etc.)
            or None if not supported/unavailable

        Raises:
            Should NOT raise exceptions. Return None on errors.
        """
        return None

    def normalise_title(self, title: str) -> str:
        """
        Normalize a film title using the standard normalization function.

        Args:
            title: Raw film title from cinema website

        Returns:
            Normalized title
        """
        return normalise_title(title)
