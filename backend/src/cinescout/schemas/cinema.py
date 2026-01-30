"""Pydantic schemas for cinema data."""

from pydantic import BaseModel, ConfigDict


class CinemaResponse(BaseModel):
    """Cinema response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    city: str
    address: str
    postcode: str
    latitude: float | None = None
    longitude: float | None = None
    website: str | None = None
    has_online_booking: bool
    supports_availability_check: bool
