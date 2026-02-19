"""Cinema model for storing cinema venue information."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.showing import Showing


class Cinema(Base, TimestampMixin):
    """
    Cinema venue model.

    Stores information about cinema venues including their scraper configuration.
    """

    __tablename__ = "cinemas"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    postcode: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Scraper configuration
    scraper_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scraper_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Pricing information
    pricing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Cinema capabilities
    has_online_booking: Mapped[bool] = mapped_column(default=True, nullable=False)
    supports_availability_check: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    showings: Mapped[list["Showing"]] = relationship(
        back_populates="cinema",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Cinema(id={self.id!r}, name={self.name!r}, city={self.city!r})>"

    def get_estimated_price(self, showing_time: datetime) -> float | None:
        """
        Calculate estimated ticket price for a showing.

        Uses pricing data with matinee/evening pricing if configured.

        Args:
            showing_time: The datetime of the showing

        Returns:
            Estimated price in GBP, or None if no pricing data available
        """
        if not self.pricing:
            return None

        # Get default price
        default_price = self.pricing.get("default")
        if default_price is None:
            return None

        # Check if matinee pricing applies
        matinee_price = self.pricing.get("matinee")
        matinee_cutoff = self.pricing.get("matinee_cutoff_hour")

        if matinee_price is not None and matinee_cutoff is not None:
            # If showing is before cutoff hour, use matinee price
            if showing_time.hour < matinee_cutoff:
                return float(matinee_price)

        return float(default_price)
