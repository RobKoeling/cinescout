"""Pydantic schemas for user accounts and authentication."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Request body for registering a new account."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=200)


class UserLogin(BaseModel):
    """Request body for logging in."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Public-facing user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    letterboxd_username: str | None = None
    letterboxd_last_synced_at: datetime | None = None


class TokenResponse(BaseModel):
    """Response for register/login — a JWT plus the user's profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
