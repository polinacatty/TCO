"""Schemas for /api/profile endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WeightPreset = Literal["balanced", "cheapest", "family", "premium", "student", "business"]


class ProfileWrite(BaseModel):
    model_config = ConfigDict(extra="ignore")

    region_id: int | None = Field(default=None, ge=0, le=100)
    annual_mileage_km: int | None = Field(default=None, ge=1000, le=200000)
    driver_age: int | None = Field(default=None, ge=16, le=99)
    driver_experience_years: int | None = Field(default=None, ge=0, le=80)
    osago_unlimited_drivers: bool = False
    use_dealer_service: bool = False
    include_kasko: bool = False
    weights_preset: WeightPreset = "balanced"

    @model_validator(mode="after")
    def _validate_experience(self) -> ProfileWrite:
        if (
            self.driver_experience_years is not None
            and self.driver_age is not None
            and self.driver_experience_years > self.driver_age - 16
        ):
            raise ValueError("driver_experience_years cannot exceed (driver_age - 16)")
        return self


class ProfileRead(ProfileWrite):
    user_id: str
    created_at: datetime
    updated_at: datetime


class ProfilePresetRequest(BaseModel):
    preset: WeightPreset


__all__ = ["ProfilePresetRequest", "ProfileRead", "ProfileWrite", "WeightPreset"]
