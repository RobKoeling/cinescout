"""Tests for the get_current_user auth dependency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from cinescout.api.dependencies import get_current_user
from cinescout.models import User


def make_credentials(token: str = "some-token"):
    creds = MagicMock()
    creds.credentials = token
    return creds


async def test_raises_401_when_no_credentials() -> None:
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None, db=db)
    assert exc_info.value.status_code == 401


async def test_raises_401_when_token_invalid() -> None:
    db = AsyncMock()
    with patch("cinescout.api.dependencies.decode_access_token", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=make_credentials(), db=db)
    assert exc_info.value.status_code == 401


async def test_raises_401_when_user_not_found_in_db() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with patch("cinescout.api.dependencies.decode_access_token", return_value=1):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=make_credentials(), db=db)
    assert exc_info.value.status_code == 401


async def test_raises_401_when_user_inactive() -> None:
    db = AsyncMock()
    user = User(id=1, username="alice", password_hash="x", is_active=False)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)

    with patch("cinescout.api.dependencies.decode_access_token", return_value=1):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=make_credentials(), db=db)
    assert exc_info.value.status_code == 401


async def test_returns_user_for_valid_token() -> None:
    db = AsyncMock()
    user = User(id=1, username="alice", password_hash="x", is_active=True)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)

    with patch("cinescout.api.dependencies.decode_access_token", return_value=1):
        resolved = await get_current_user(credentials=make_credentials(), db=db)
    assert resolved is user
