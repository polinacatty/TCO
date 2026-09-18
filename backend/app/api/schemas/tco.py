"""Pydantic v2 схемы для POST /api/tco/calculate."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ComponentCode = Literal[
    "depreciation",
    "fuel",
    "osago",
    "kasko",
    "transport_tax",
    "maintenance",
    "tyres",
]


# --------------------------------------------------------------------------- #
# Request                                                                     #
# --------------------------------------------------------------------------- #


class ProfileInput(BaseModel):
    """Профиль владения, передаваемый клиентом"""

    model_config = ConfigDict(extra="ignore")

    region_id: int = Field(ge=0, le=100)
    annual_mileage_km: int = Field(ge=1_000, le=200_000)
    driver_age: int | None = Field(default=None, ge=16, le=99)
    driver_experience_years: int | None = Field(default=None, ge=0, le=80)
    osago_unlimited_drivers: bool = False
    use_dealer_service: bool = False
    include_kasko: bool = False

    @model_validator(mode="after")
    def _check_experience(self) -> ProfileInput:
        if (
            self.driver_age is not None
            and self.driver_experience_years is not None
            and self.driver_experience_years > self.driver_age - 16
        ):
            raise ValueError(
                "driver_experience_years cannot exceed"
            )
        return self


class TcoOptionsInput(BaseModel):
    """Опции расчёта."""

    model_config = ConfigDict(extra="ignore")

    include_kasko: bool | None = None
    discount_rate_pct: float = Field(default=0.0, ge=0.0, le=30.0)


class TcoCalculateRequest(BaseModel):
    """POST /api/tco/calculate."""

    model_config = ConfigDict(extra="ignore")

    modification_id: int = Field(ge=1)
    purchase_price_rub: int | None = Field(default=None, ge=0, le=1_000_000_000)
    year_of_manufacture: int | None = Field(default=None, ge=1990, le=2100)
    horizon_years: int = Field(default=5, ge=1, le=10)
    profile: ProfileInput
    options: TcoOptionsInput = Field(default_factory=TcoOptionsInput)


# --------------------------------------------------------------------------- #
# Response                                                                    #
# --------------------------------------------------------------------------- #


class ComponentResult(BaseModel):

    total_rub: int
    share_pct: float = Field(ge=0.0, le=100.0)
    details: dict[str, Any] = Field(default_factory=dict)


class TcoYearly(BaseModel):
    """Годовой агрегат."""

    year_index: int = Field(ge=1)
    total_rub: int
    by_component: dict[ComponentCode, int]
    cumulative_rub: int


class TcoMeta(BaseModel):
    """Метаданные ответа."""

    profile_hash: str
    cached: bool = False
    computed_at: datetime
    models_versions: dict[str, str] = Field(default_factory=dict)
    scope_disclaimer_ru: str
    included_items_ru: list[str]
    excluded_items_ru: list[str]


class TcoCalculateResponse(BaseModel):
    """Полный ответ POST /api/tco/calculate."""

    modification_id: int
    horizon_years: int
    purchase_price_rub: int
    predicted_resale_price_rub: int
    total_tco_rub: int
    total_tco_per_km_rub: float
    components: dict[ComponentCode, ComponentResult]
    yearly: list[TcoYearly]
    meta: TcoMeta


__all__ = [
    "ProfileInput",
    "TcoOptionsInput",
    "TcoCalculateRequest",
    "ComponentResult",
    "TcoYearly",
    "TcoMeta",
    "TcoCalculateResponse",
    "ComponentCode",
]
