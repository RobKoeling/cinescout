"""Showing model for film screening times at cinemas."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.cinema import Cinema
    from cinescout.models.film import Film


class Showing(Base, TimestampMixin):
    """
    Film showing/screening model.

    Links a cinema, film, and specific screening time.
    Includes booking information and screen details.
    """

    __tablename__ = "showings"
    __table_args__ = (
        UniqueConstraint(
            "cinema_id",
            "film_id",
            "start_time",
            name="uq_cinema_film_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign keys
    cinema_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("cinemas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    film_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Showing details
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    booking_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    screen_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format_tags: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Debugging: store the original title from the cinema website
    raw_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    cinema: Mapped["Cinema"] = relationship(back_populates="showings")
    film: Mapped["Film"] = relationship(back_populates="showings")

    def __repr__(self) -> str:
        return (
            f"<Showing(cinema_id={self.cinema_id!r}, "
            f"film_id={self.film_id!r}, "
            f"start_time={self.start_time})>"
        )
