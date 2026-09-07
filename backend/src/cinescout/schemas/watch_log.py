"""Pydantic schemas for watch-log entries."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cinescout.schemas.cinema import CinemaResponse
from cinescout.schemas.film import FilmResponse


class WatchLogCreate(BaseModel):
    """
    Create a watch-log entry.

    Exactly one of showing_id or (film_id + watched_date) must be given:
    - showing_id set  -> tracked-showing entry; film_id/watched_date are
      derived server-side from the showing, ignoring any client values.
    - showing_id None -> manual entry; film_id and watched_date are required.
    """

    showing_id: int | None = None
    film_id: str | None = None
    watched_date: date | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5.0, multiple_of=0.5)
    comment: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def check_showing_or_manual(self) -> "WatchLogCreate":
        if self.showing_id is None and (self.film_id is None or self.watched_date is None):
            raise ValueError(
                "film_id and watched_date are required for a manual watch-log entry "
                "(when showing_id is not provided)"
            )
        return self


class WatchLogResponse(BaseModel):
    """A watch-log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    film_id: str
    showing_id: int | None
    watched_date: date
    rating: float | None
    comment: str | None
    created_at: datetime


class WatchLogWithFilmResponse(WatchLogResponse):
    """Diary list response — embeds film/cinema so no extra frontend fetch is needed."""

    film: FilmResponse
    cinema: CinemaResponse | None = None
