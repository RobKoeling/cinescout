"""Film alias model for mapping cinema-specific titles to canonical films."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.film import Film


class FilmAlias(Base, TimestampMixin):
    """
    Film alias model.

    Maps cinema-specific film titles (normalized) to canonical film records.
    Used to speed up film matching by avoiding repeated fuzzy matches.
    """

    __tablename__ = "film_aliases"
    __table_args__ = (UniqueConstraint("normalized_title", name="uq_normalized_title"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    film_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    film: Mapped["Film"] = relationship(back_populates="aliases")

    def __repr__(self) -> str:
        return f"<FilmAlias(normalized_title={self.normalized_title!r}, film_id={self.film_id!r})>"
