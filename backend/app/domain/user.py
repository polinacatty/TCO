"""Domain DTOs for auth/profile use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UserSnapshot:
    id: str
    email: str
    password_hash: str
    pdn_consent: bool
    is_active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshTokenSnapshot:
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UserProfileSnapshot:
    user_id: str
    region_id: int | None
    annual_mileage_km: int | None
    driver_age: int | None
    driver_experience_years: int | None
    osago_unlimited_drivers: bool
    use_dealer_service: bool
    include_kasko: bool
    weights_preset: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class FavoriteModificationSnapshot:
    user_id: str
    modification_id: int
    created_at: datetime


__all__ = [
    "RefreshTokenSnapshot",
    "UserProfileSnapshot",
    "UserSnapshot",
    "FavoriteModificationSnapshot",
]
