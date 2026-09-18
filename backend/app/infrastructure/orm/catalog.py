"""Catalog ORM: regions + car_* + tire_*.
    regions.csv             -> regions
    car_makes.csv           -> car_makes
    car_models.csv          -> car_models
    car_generations.csv     -> car_generations
    car_modifications.parquet -> car_modifications
    tire_sizes.csv          -> tire_sizes
    tire_size_prices.csv    -> tire_size_prices
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm.base import Base


class Region(Base):
    """85 регионов РФ."""

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    iso_code: Mapped[str] = mapped_column(String(8), nullable=False)
    federal_district: Mapped[str] = mapped_column(String(64), nullable=False)
    climate_zone: Mapped[str] = mapped_column(String(32), nullable=False)
    population_thousands: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CarMake(Base):
    """Производители."""

    __tablename__ = "car_makes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name_normalized: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)


class CarModel(Base):
    """Модели."""

    __tablename__ = "car_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make_id: Mapped[int] = mapped_column(
        ForeignKey("car_makes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    segment: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    body_type: Mapped[str] = mapped_column(String(32), nullable=False)


class CarGeneration(Base):
    """Поколения."""

    __tablename__ = "car_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("car_models.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    year_from: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    year_to: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    restyling: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class CarModification(Base):
    """Модификации."""

    __tablename__ = "car_modifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generation_id: Mapped[int] = mapped_column(
        ForeignKey("car_generations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trim_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    engine_volume_l: Mapped[float] = mapped_column(Float, nullable=False)
    power_hp: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    torque_nm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    fuel_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    transmission: Mapped[str] = mapped_column(String(16), nullable=False)
    drive: Mapped[str] = mapped_column(String(16), nullable=False)

    fuel_consumption_combined_l_100km: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_consumption_city_l_100km: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_consumption_highway_l_100km: Mapped[float | None] = mapped_column(Float, nullable=True)

    length_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    curb_weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seats: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cargo_volume_l: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_clearance_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    msrp_new_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False)

    msrp_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reliability_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enriched_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class TireSize(Base):
    """размеры шин по модификациям."""

    __tablename__ = "tire_sizes"

    modification_id: Mapped[int] = mapped_column(
        ForeignKey("car_modifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    axle: Mapped[str] = mapped_column(String(8), nullable=False)
    size_code: Mapped[str] = mapped_column(String(16), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (PrimaryKeyConstraint("modification_id", "axle", name="pk_tire_sizes"),)


class TireSizePrice(Base):
    """цены комплектов шин по размеру и сезону."""

    __tablename__ = "tire_size_prices"

    size_code: Mapped[str] = mapped_column(String(16), nullable=False)
    season: Mapped[str] = mapped_column(String(8), nullable=False)
    avg_set_price_rub: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("size_code", "season", name="pk_tire_size_prices"),
    )


__all__ = [
    "Region",
    "CarMake",
    "CarModel",
    "CarGeneration",
    "CarModification",
    "TireSize",
    "TireSizePrice",
]
