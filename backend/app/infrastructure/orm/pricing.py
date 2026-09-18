"""Pricing references ORM: ОСАГО, налоги, амортизация, КАСКО, ТО, топливо, ЦБ."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm.base import Base

# --------------------------------------------------------------------------- #
# ОСАГО                                                                       #
# --------------------------------------------------------------------------- #


class OsagoBaseTariff(Base):
    """Базовые тарифы ТБ для категорий ТС."""

    __tablename__ = "osago_base_tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    category_label: Mapped[str] = mapped_column(String(128), nullable=False)
    vehicle_categories: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tb_min_rub: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tb_max_rub: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class OsagoTerritoryCoef(Base):
    """Территориальные коэффициенты KT по регионам."""

    __tablename__ = "osago_territory_coefs"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), primary_key=True
    )
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    kt_capital_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kt_general: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    kt_special: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OsagoPower(Base):
    """KM — коэффициент мощности по диапазонам hp для семейств ТС."""

    __tablename__ = "osago_power"

    vehicle_family: Mapped[str] = mapped_column(String(32), nullable=False)
    power_min_hp_excl: Mapped[int] = mapped_column(Integer, nullable=False)
    power_max_hp_incl: Mapped[int] = mapped_column(Integer, nullable=False)
    km_value: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "vehicle_family",
            "power_min_hp_excl",
            "power_max_hp_incl",
            name="pk_osago_power",
        ),
    )


class OsagoKbm(Base):
    """Класс водителя и его коэффициент KBM."""

    __tablename__ = "osago_kbm"

    kbm_class: Mapped[str] = mapped_column(String(2), primary_key=True)
    kbm_value: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    class_after_no_claim: Mapped[str] = mapped_column(String(2), nullable=False)
    class_after_1_claim: Mapped[str] = mapped_column(String(2), nullable=False)
    class_after_2_claims: Mapped[str] = mapped_column(String(2), nullable=False)
    class_after_3_claims: Mapped[str] = mapped_column(String(2), nullable=False)
    class_after_more_than_3_claims: Mapped[str] = mapped_column(String(2), nullable=False)


class OsagoAgeExp(Base):
    """KVS — коэффициент возраст+стаж."""

    __tablename__ = "osago_age_exp"

    vehicle_family: Mapped[str] = mapped_column(String(32), nullable=False)
    age_min_incl: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    age_max_incl: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    exp_min_years_incl: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    exp_max_years_excl: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    kvs_value: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "vehicle_family",
            "age_min_incl",
            "exp_min_years_incl",
            name="pk_osago_age_exp",
        ),
    )


class OsagoDrivers(Base):
    """KO — коэффициент ограниченности круга водителей."""

    __tablename__ = "osago_drivers"

    restricted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ko_value: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("restricted", "owner_type", name="pk_osago_drivers"),
    )


class OsagoSeasonal(Base):
    """KS — коэффициент сезонности."""

    __tablename__ = "osago_seasonal"

    period_min_months_excl: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    period_max_months_incl: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ks_value: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "period_min_months_excl",
            "period_max_months_incl",
            name="pk_osago_seasonal",
        ),
    )


# --------------------------------------------------------------------------- #
# Налоги                                                                      #
# --------------------------------------------------------------------------- #


class TransportTaxRate(Base):
    """Ставки транспортного налога по регионам и диапазонам л. с."""

    __tablename__ = "transport_tax_rates"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    hp_min: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    hp_max: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    rate_rub_per_hp: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("region_id", "hp_min", name="pk_transport_tax_rates"),
    )


class LuxuryCar(Base):
    """Список премиум-моделей Минпромторга для повышающего коэффициента."""

    __tablename__ = "luxury_cars"

    make: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    engine_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    engine_volume_l: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    price_tier_min_rub: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("make", "model", "price_tier_min_rub", name="pk_luxury_cars"),
    )


# --------------------------------------------------------------------------- #
# Амортизация (ADR-0001)                                                      #
# --------------------------------------------------------------------------- #


class DepreciationRate(Base):
    """Годовые ставки амортизации по (segment, brand_tier, age_bucket)."""

    __tablename__ = "depreciation_rates"

    segment: Mapped[str] = mapped_column(String(16), nullable=False)
    brand_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    age_year_bucket: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    annual_depreciation_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "segment", "brand_tier", "age_year_bucket", name="pk_depreciation_rates"
        ),
    )


class MileagePenalty(Base):
    """Штраф к амортизации за повышенный пробег (порог -> +%)."""

    __tablename__ = "mileage_penalties"

    mileage_threshold_km: Mapped[int] = mapped_column(Integer, primary_key=True)
    extra_depreciation_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)


# --------------------------------------------------------------------------- #
# КАСКО                                                                       #
# --------------------------------------------------------------------------- #


class KaskoRate(Base):
    """Базовые ставки КАСКО по (brand_tier, segment, age_bucket)."""

    __tablename__ = "kasko_rates"

    brand_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    segment: Mapped[str] = mapped_column(String(16), nullable=False)
    age_year_bucket: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    kasko_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "brand_tier", "segment", "age_year_bucket", name="pk_kasko_rates"
        ),
    )


# --------------------------------------------------------------------------- #
# Плановое ТО                                                                 #
# --------------------------------------------------------------------------- #


class ServiceOperation(Base):
    """Справочник плановых операций ТО."""

    __tablename__ = "service_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    default_norm_hours: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)


class ServicePlanOp(Base):
    """План ТО для поколения: операция × (каждые N км ИЛИ каждые N месяцев)."""

    __tablename__ = "service_plan_ops"

    generation_id: Mapped[int] = mapped_column(
        ForeignKey("car_generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_id: Mapped[int] = mapped_column(
        ForeignKey("service_operations.id", ondelete="RESTRICT"), nullable=False
    )
    every_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    every_months: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("generation_id", "operation_id", name="pk_service_plan_ops"),
    )


class PartsCost(Base):
    """Средняя стоимость запчасти под одну операцию для (brand_segment)."""

    __tablename__ = "parts_costs"

    operation_id: Mapped[int] = mapped_column(
        ForeignKey("service_operations.id", ondelete="RESTRICT"), nullable=False
    )
    operation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_segment: Mapped[str] = mapped_column(String(32), nullable=False)
    avg_parts_cost_rub: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "operation_id", "brand_segment", name="pk_parts_costs"
        ),
    )


class LaborRate(Base):
    """Стоимость нормо-часа СТО по региону и типу СТО."""

    __tablename__ = "labor_rates"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sto_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rate_rub_per_hour: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("region_id", "sto_type", name="pk_labor_rates"),
    )


# --------------------------------------------------------------------------- #
# Топливо                                                                     #
# --------------------------------------------------------------------------- #


class FuelPrice(Base):
    """Исторические наблюдённые цены на топливо."""

    __tablename__ = "fuel_prices"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    fuel_type: Mapped[str] = mapped_column(String(16), nullable=False)
    price_month: Mapped[date] = mapped_column(Date, nullable=False)
    price_rub_per_l: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "region_id", "fuel_type", "price_month", name="pk_fuel_prices"
        ),
    )


class FuelPriceForecast(Base):

    __tablename__ = "fuel_price_forecast"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    fuel_type: Mapped[str] = mapped_column(String(16), nullable=False)
    price_month: Mapped[date] = mapped_column(Date, nullable=False)
    price_rub_per_l: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)

    forecast_origin_month: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_step: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    model_version: Mapped[str] = mapped_column(String(16), nullable=False)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "region_id", "fuel_type", "price_month", name="pk_fuel_price_forecast"
        ),
    )


# --------------------------------------------------------------------------- #
# Курсы ЦБ (для расширений; не используется в TCO MVP)                        #
# --------------------------------------------------------------------------- #


class CbrRate(Base):
    """Ключевая ставка ЦБ + курсы валют по дням."""

    __tablename__ = "cbr_rates"

    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("metric_date", "metric_type", name="pk_cbr_rates"),
    )


__all__ = [
    "OsagoBaseTariff",
    "OsagoTerritoryCoef",
    "OsagoPower",
    "OsagoKbm",
    "OsagoAgeExp",
    "OsagoDrivers",
    "OsagoSeasonal",
    "TransportTaxRate",
    "LuxuryCar",
    "DepreciationRate",
    "MileagePenalty",
    "KaskoRate",
    "ServiceOperation",
    "ServicePlanOp",
    "PartsCost",
    "LaborRate",
    "FuelPrice",
    "FuelPriceForecast",
    "CbrRate",
]
