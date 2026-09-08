"""Pydantic schemas for Letterboxd account linking and diary import."""

from pydantic import BaseModel, Field


class LetterboxdLinkRequest(BaseModel):
    """Request body for linking a Letterboxd username."""

    letterboxd_username: str = Field(min_length=1, max_length=100)


class LetterboxdImportResponse(BaseModel):
    """Result summary for a diary import."""

    status: str
    entries_found: int
    entries_imported: int
    entries_skipped_duplicate: int
    entries_unmatched: int
