"""Pydantic schemas for film data."""

from pydantic import BaseModel, ConfigDict


class FilmBase(BaseModel):
    """Base film schema with common fields."""

    title: str
    year: int | None = None
    directors: list[str] | None = None
    countries: list[str] | None = None
    runtime: int | None = None
    overview: str | None = None
    poster_path: str | None = None
    tmdb_id: int | None = None


class FilmResponse(FilmBase):
    """Film response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str


class FilmWithShowingCount(FilmResponse):
    """Film response with showing count for search results."""

    showing_count: int
