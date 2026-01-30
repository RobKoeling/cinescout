"""Data models for scrapers."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawShowing:
    """
    Raw showing data from a cinema scraper.

    This is the output format that all scrapers must return.
    The film matching service will process the title and create proper database records.
    """

    title: str  # Film title as it appears on cinema website
    start_time: datetime  # Showing time (timezone-aware)
    booking_url: str | None = None  # URL to book tickets
    screen_name: str | None = None  # Screen/auditorium name
    format_tags: str | None = None  # e.g., "35mm", "IMAX", "Subtitled"
    price: float | None = None  # Ticket price in GBP

    def __post_init__(self) -> None:
        """Validate that start_time is timezone-aware."""
        if self.start_time.tzinfo is None:
            raise ValueError("start_time must be timezone-aware")
