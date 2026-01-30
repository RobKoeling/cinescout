"""Pydantic schemas for showing data."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from cinescout.schemas.cinema import CinemaResponse
from cinescout.schemas.film import FilmWithShowingCount


class ShowingTimeResponse(BaseModel):
    """Individual showing time response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    screen_name: str | None = None
    format_tags: str | None = None
    booking_url: str | None = None
    price: float | None = None


class CinemaWithShowings(BaseModel):
    """Cinema with its showing times for a specific film."""

    cinema: CinemaResponse
    times: list[ShowingTimeResponse]


class FilmWithCinemas(BaseModel):
    """Film with all cinemas showing it."""

    film: FilmWithShowingCount
    cinemas: list[CinemaWithShowings]


class ShowingsQuery(BaseModel):
    """Query parameters for showings search."""

    date: date
    city: str = "london"
    time_from: time = Field(default_factory=lambda: time(0, 0))
    time_to: time = Field(default_factory=lambda: time(23, 59))


class ShowingsResponse(BaseModel):
    """Response for showings endpoint."""

    films: list[FilmWithCinemas]
    total_films: int
    total_showings: int
    query: ShowingsQuery
