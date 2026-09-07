"""Authentication API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.api.dependencies import get_current_user
from cinescout.database import get_db
from cinescout.models import User
from cinescout.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from cinescout.services.auth_service import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Create a new account and return an access token."""
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Log in with a username and password, returning an access token."""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the current user — used by the frontend to validate a stored token."""
    return UserResponse.model_validate(user)
