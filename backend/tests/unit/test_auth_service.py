"""Tests for password hashing and JWT helpers."""

from datetime import datetime, timedelta, timezone

import jwt

from cinescout.config import settings
from cinescout.services.auth_service import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_and_verify_roundtrip() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_produces_60_char_bcrypt_hash() -> None:
    hashed = hash_password("some-password")
    assert len(hashed) == 60


def test_verify_password_returns_false_for_malformed_hash() -> None:
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_create_and_decode_access_token_roundtrip() -> None:
    token = create_access_token(user_id=42)
    assert decode_access_token(token) == 42


def test_decode_access_token_returns_none_for_garbage_token() -> None:
    assert decode_access_token("this.is.not.a.jwt") is None


def test_decode_access_token_returns_none_for_expired_token() -> None:
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": "1",
        "iat": now - timedelta(days=31),
        "exp": now - timedelta(days=1),
    }
    token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    assert decode_access_token(token) is None


def test_decode_access_token_returns_none_for_wrong_secret() -> None:
    now = datetime.now(timezone.utc)
    payload = {"sub": "1", "iat": now, "exp": now + timedelta(days=1)}
    token = jwt.encode(payload, "a-different-secret", algorithm=JWT_ALGORITHM)
    assert decode_access_token(token) is None
