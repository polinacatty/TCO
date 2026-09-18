"""Schemas for /api/auth endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    pdn_consent: bool


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=5, max_length=320)


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=8, max_length=256)


class UserRead(BaseModel):
    id: str
    email: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserRead
    access_token: str
    expires_in: int


class MeResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    has_profile: bool


__all__ = [
    "AuthResponse",
    "LoginRequest",
    "PasswordResetRequest",
    "PasswordResetConfirmRequest",
    "MeResponse",
    "RegisterRequest",
    "UserRead",
]
