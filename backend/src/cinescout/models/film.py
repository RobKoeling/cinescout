"""Film model for storing film metadata."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinescout.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from cinescout.models.film_alias import FilmAlias
    from cinescout.models.showing import Showing


class Film(Base, TimestampMixin):
    """
    Film model.

    Stores film metadata from TMDb or placeholder data.
    Uses PostgreSQL ARRAY type for directors and countries.
    """

    __tablename__ = "films"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # TMDb metadata
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    directors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    countries: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    runtime: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    showings: Mapped[list["Showing"]] = relationship(
        back_populates="film",
        cascade="all, delete-orphan",
    )
    aliases: Mapped[list["FilmAlias"]] = relationship(
        back_populates="film",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Film(id={self.id!r}, title={self.title!r}, year={self.year})>"
