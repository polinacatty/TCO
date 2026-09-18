"""Pydantic v2 схемы caталог-эндпоинтов."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegionRead(BaseModel):
    """Регион РФ для выпадающего списка в UI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    iso_code: str
    federal_district: str
    climate_zone: str


class MakeRead(BaseModel):
    """Марка автомобиля."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    brand_tier: str = Field(
        description="russian | mass | japanese_korean_mass | premium | chinese"
    )


class ModelRead(BaseModel):
    """Модель в рамках марки."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    make_id: int
    name: str
    segment: str = Field(description="A | B | C | D | E | F | J_SUV | J_CROSS | M_MPV | LCV | S_SPORT")
    body_type: str


class GenerationRead(BaseModel):
    """Поколение модели."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    model_id: int
    name: str
    year_from: int
    year_to: int | None = None
    restyling: int = 0


class ModificationRead(BaseModel):
    """Slim-карточка модификации."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    make: str
    model: str
    generation: str
    trim_name: str | None = None
    year_from: int
    year_to: int | None = None
    body_type: str
    segment: str
    power_hp: int
    engine_volume_l: float | None = None
    fuel_type: str
    transmission: str
    drive: str
    fuel_consumption_combined_l_100km: float
    msrp_new_rub: int


__all__ = [
    "RegionRead",
    "MakeRead",
    "ModelRead",
    "GenerationRead",
    "ModificationRead",
]
