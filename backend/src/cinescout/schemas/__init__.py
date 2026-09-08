"""Pydantic schemas for API requests and responses."""

from cinescout.schemas.cinema import CinemaResponse
from cinescout.schemas.film import FilmResponse, FilmWithShowingCount
from cinescout.schemas.showing import (
    CinemaWithShowings,
    FilmWithCinemas,
    ShowingsQuery,
    ShowingsResponse,
    ShowingTimeResponse,
)
from cinescout.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse

__all__ = [
    "CinemaResponse",
    "FilmResponse",
    "FilmWithShowingCount",
    "ShowingTimeResponse",
    "CinemaWithShowings",
    "FilmWithCinemas",
    "ShowingsQuery",
    "ShowingsResponse",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserResponse",
]
