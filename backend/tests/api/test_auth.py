"""Tests for the authentication API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from cinescout.api.dependencies import get_current_user
from cinescout.api.routes import auth
from cinescout.database import get_db
from cinescout.models import User
from cinescout.services.auth_service import hash_password

REGISTER_PAYLOAD = {"username": "alice", "password": "correct-horse-battery-staple"}
LOGIN_PAYLOAD = {"username": "alice", "password": "correct-horse-battery-staple"}


def make_user(
    id: int = 1,
    username: str = "alice",
    password: str = "correct-horse-battery-staple",
    is_active: bool = True,
) -> User:
    return User(id=id, username=username, password_hash=hash_password(password), is_active=is_active)


def make_db(execute_result=None, flush_side_effect=None):
    async def _override():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=execute_result or MagicMock())
        if flush_side_effect is not None:
            db.flush = AsyncMock(side_effect=flush_side_effect)
        # Simulate the DB assigning an autoincrement id on add(), like a real flush would.
        db.add = MagicMock(side_effect=lambda obj: setattr(obj, "id", 1))
        yield db

    return _override


@pytest.fixture
def auth_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router)
    return app


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


async def test_register_creates_user_and_returns_token(auth_app: FastAPI) -> None:
    auth_app.dependency_overrides[get_db] = make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice"


async def test_register_returns_409_on_duplicate_username(auth_app: FastAPI) -> None:
    auth_app.dependency_overrides[get_db] = make_db(
        flush_side_effect=IntegrityError("duplicate", {}, Exception())
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]


async def test_register_rejects_short_password(auth_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        response = await client.post(
            "/auth/register", json={"username": "alice", "password": "short"}
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


async def test_login_returns_token_for_valid_credentials(auth_app: FastAPI) -> None:
    user = make_user()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    auth_app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.post("/auth/login", json=LOGIN_PAYLOAD)
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["user"]["username"] == "alice"


async def test_login_returns_401_for_wrong_password(auth_app: FastAPI) -> None:
    user = make_user()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    auth_app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.post(
                "/auth/login", json={"username": "alice", "password": "wrong-password"}
            )
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 401


async def test_login_returns_401_for_unknown_username(auth_app: FastAPI) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    auth_app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.post("/auth/login", json=LOGIN_PAYLOAD)
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 401


async def test_login_returns_401_for_inactive_user(auth_app: FastAPI) -> None:
    user = make_user(is_active=False)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    auth_app.dependency_overrides[get_db] = make_db(execute_result=result)
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.post("/auth/login", json=LOGIN_PAYLOAD)
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


async def test_get_me_returns_current_user(auth_app: FastAPI) -> None:
    user = make_user()
    auth_app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.get("/auth/me", headers={"Authorization": "Bearer irrelevant"})
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


async def test_get_me_returns_401_without_token(auth_app: FastAPI) -> None:
    auth_app.dependency_overrides[get_db] = make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
            response = await client.get("/auth/me")
    finally:
        auth_app.dependency_overrides.clear()

    assert response.status_code == 401
