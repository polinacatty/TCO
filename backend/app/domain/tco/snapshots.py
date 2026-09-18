"""Snapshots — read-only DTOs returned by repositories to the domain.

Repositories build these once per request (eagerly fetching the data needed
for the full calculation) and pass them to the calculator. The calculator
then works on plain Python objects without touching the database again.

This keeps the domain layer 100 % free of SQLAlchemy / asyncio while still
allowing the implementation to be async at the infrastructure level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RegionSnapshot:
    """Read-only view of one row from ``regions`` (catalog list)."""

    id: int
    name: str
    iso_code: str
    federal_district: str
    climate_zone: str


@dataclass(frozen=True, slots=True)
class MakeSnapshot:
    """Read-only view of one row from ``car_makes`` (catalog list)."""

    id: int
    name: str
    country: str
    brand_tier: str


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    """Read-only view of one row from ``car_models`` (catalog list)."""

    id: int
    make_id: int
    name: str
    segment: str
    body_type: str


@dataclass(frozen=True, slots=True)
class GenerationSnapshot:
    """Read-only view of one row from ``car_generations`` (catalog list)."""

    id: int
    model_id: int
    name: str
    year_from: int
    year_to: int | None
    restyling: int


@dataclass(frozen=True, slots=True)
class ModificationListItemSnapshot:
    """Slim view of ``car_modifications`` for catalog/listing.

    Carries the parent labels (``make_name`` / ``model_name`` / ``generation_name``)
    so the API layer can render breadcrumbs without joining again.
    """

    id: int
    make_name: str
    model_name: str
    generation_name: str
    trim_name: str | None
    year_from: int
    year_to: int | None
    body_type: str
    segment: str
    power_hp: int
    engine_volume_l: Decimal | None
    fuel_type: str
    transmission: str
    drive: str
    fuel_consumption_combined_l_100km: Decimal
    msrp_new_rub: int
    reliability_score: float | None = None
    cargo_volume_l: int | None = None
    seats: int | None = None
    body_clearance_mm: int | None = None


@dataclass(frozen=True, slots=True)
class CarSnapshot:
    """Read-only view of a car modification + its parent generation / model / make.

    Holds every field the TCO calculator can possibly need; computed once at
    the start of the request so individual components don't re-query the DB.
    """

    modification_id: int
    generation_id: int
    model_id: int
    make_id: int

    make_name: str
    model_name: str
    brand_tier: str
    country: str | None
    segment: str

    msrp_new_rub: int
    power_hp: int
    engine_volume_l: Decimal | None
    fuel_type: str
    fuel_consumption_combined_l_100km: Decimal | None


@dataclass(frozen=True, slots=True)
class TireSizeSnapshot:
    """One row from ``tire_sizes`` (per modification, possibly staggered)."""

    size_code: str
    axle: str  # "both" | "front" | "rear"


@dataclass(frozen=True, slots=True)
class TirePriceSnapshot:
    """Summer + winter price for one size code, from ``tire_size_prices``."""

    size_code: str
    summer_price_rub: int
    winter_price_rub: int


@dataclass(frozen=True, slots=True)
class DepreciationRateSnapshot:
    """One row from ``depreciation_rates`` (segment × brand_tier × age)."""

    segment_6: str
    brand_tier: str
    age_year_bucket: int  # 1..5; bucket 5 means "5+"
    annual_depreciation_pct: Decimal


@dataclass(frozen=True, slots=True)
class MileagePenaltySnapshot:
    """One row from ``mileage_penalties`` — threshold → extra pct."""

    mileage_threshold_km: int
    extra_depreciation_pct: Decimal


@dataclass(frozen=True, slots=True)
class KaskoRateSnapshot:
    """One row from ``kasko_rates`` (tier × segment × age)."""

    brand_tier: str
    segment_6: str
    age_year_bucket: int
    kasko_rate_pct: Decimal


@dataclass(frozen=True, slots=True)
class OsagoCoefficientsSnapshot:
    """Pre-resolved OSAGO coefficients for the current request.

    The catalog tables (``osago_*``) are tiny, so we resolve all coefficients
    in one trip to the DB and hand the resulting bundle to the calculator.
    This avoids a 7-coefficient lookup spread across the components.
    """

    tb_min_rub: Decimal
    tb_max_rub: Decimal
    kt_general: Decimal
    km_value: Decimal
    kvs_value: Decimal
    ko_value: Decimal
    kbm_value: Decimal = Decimal("1.00")
    ks_value: Decimal = Decimal("1.00")

    @property
    def tb_mid_rub(self) -> Decimal:
        """Mid-corridor base tariff (mid is used by the model — see methodology §3.2)."""
        return (self.tb_min_rub + self.tb_max_rub) / 2


@dataclass(frozen=True, slots=True)
class TransportTaxRateSnapshot:
    """One row from ``transport_tax_rates`` for a given (region, hp bracket)."""

    region_id: int
    hp_min: int
    hp_max: int
    rate_rub_per_hp: Decimal


@dataclass(frozen=True, slots=True)
class LuxuryCarSnapshot:
    """One row from ``luxury_car_list`` — used to check inclusion + bracket."""

    make_name: str
    model_name: str
    engine_type: str | None
    engine_volume_l: Decimal | None
    price_tier_min_rub: int  # 10_000_000 or 15_000_000


@dataclass(frozen=True, slots=True)
class ServicePlanOpSnapshot:
    """One row from ``service_plan_ops`` for a given generation."""

    operation_id: int
    operation_code: str
    default_norm_hours: Decimal
    every_km: int | None
    every_months: int | None


@dataclass(frozen=True, slots=True)
class PartsCostSnapshot:
    """One row from ``parts_costs`` (operation × brand_segment)."""

    operation_id: int
    brand_segment: str
    avg_parts_cost_rub: int


@dataclass(frozen=True, slots=True)
class LaborRateSnapshot:
    """One row from ``labor_rates`` — ₽/час for (region, sto_type)."""

    region_id: int
    sto_type: str
    rate_rub_per_hour: int


@dataclass(frozen=True, slots=True)
class FuelPriceForecastSnapshot:
    """Single (region, fuel, month) row from ``fuel_price_forecast``."""

    region_id: int
    fuel_type: str
    price_month: date
    price_rub_per_l: Decimal


__all__ = [
    "RegionSnapshot",
    "MakeSnapshot",
    "ModelSnapshot",
    "GenerationSnapshot",
    "ModificationListItemSnapshot",
    "CarSnapshot",
    "TireSizeSnapshot",
    "TirePriceSnapshot",
    "DepreciationRateSnapshot",
    "MileagePenaltySnapshot",
    "KaskoRateSnapshot",
    "OsagoCoefficientsSnapshot",
    "TransportTaxRateSnapshot",
    "LuxuryCarSnapshot",
    "ServicePlanOpSnapshot",
    "PartsCostSnapshot",
    "LaborRateSnapshot",
    "FuelPriceForecastSnapshot",
]
