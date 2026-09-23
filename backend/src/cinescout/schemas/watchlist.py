"""Pydantic schemas for a user's film watchlist."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from cinescout.schemas.cinema import CinemaResponse
from cinescout.schemas.film import FilmResponse


class WatchlistItemResponse(BaseModel):
    """A film on the user's watchlist."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    film_id: str
    created_at: datetime
    film: FilmResponse


class UpcomingWatchlistShowingResponse(BaseModel):
    """An upcoming showing of a film on the user's watchlist — the heads-up."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    booking_url: str | None
    screen_name: str | None
    format_tags: str | None
    film: FilmResponse
    cinema: CinemaResponse
