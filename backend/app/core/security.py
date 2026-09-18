"""Password hashing + JWT helpers for auth/profile."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import Settings, get_settings
from app.core.exceptions import ValidationAppError

_PH = PasswordHasher()


def hash_password(raw_password: str) -> str:
    return _PH.hash(raw_password)


def verify_password(raw_password: str, hashed: str) -> bool:
    try:
        return _PH.verify(hashed, raw_password)
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    user_id: str,
    email: str,
    settings: Settings | None = None,
) -> tuple[str, int]:
    s = settings or get_settings()
    expires_in = s.jwt_access_ttl_min * 60
    exp = datetime.now(UTC) + timedelta(seconds=expires_in)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ValidationAppError("invalid access token") from exc
    if payload.get("type") != "access":
        raise ValidationAppError("invalid access token type")
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

