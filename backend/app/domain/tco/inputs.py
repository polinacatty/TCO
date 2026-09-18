"""Inputs for the TCO calculator — bundles the user profile, car, and snapshots.

The service layer (etap 3+) is responsible for:

1. Resolving ``modification_id`` → :class:`CarSnapshot`
2. Pre-loading all reference rows the calculator needs into a :class:`TcoContext`
3. Calling ``TcoCalculator.compute(profile, context)``

The calculator itself never touches the DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    FuelPriceForecastSnapshot,
    KaskoRateSnapshot,
    LaborRateSnapshot,
    LuxuryCarSnapshot,
    MileagePenaltySnapshot,
    OsagoCoefficientsSnapshot,
    PartsCostSnapshot,
    ServicePlanOpSnapshot,
    TirePriceSnapshot,
    TireSizeSnapshot,
    TransportTaxRateSnapshot,
)


@dataclass(frozen=True, slots=True)
class TcoContext:
    """All reference data the calculator needs, pre-fetched by repositories.

    The shape mirrors the seven TCO components: each block of fields is the
    minimal cut of the corresponding reference table for *this* request.

    ``calculation_start_date`` is normally "today" (UTC date) and used as
    the anchor for both the fuel-forecast month index and the tax year
    sequence. Service layer should fix it once per request for reproducibility.
    """

    car: CarSnapshot
    calculation_start_date: date

    # transport tax
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...] = field(default_factory=tuple)
    luxury_matches: tuple[LuxuryCarSnapshot, ...] = field(default_factory=tuple)

    # OSAGO — pre-resolved bundle
    osago_coefficients: OsagoCoefficientsSnapshot | None = None

    # depreciation
    depreciation_rates: tuple[DepreciationRateSnapshot, ...] = field(default_factory=tuple)
    mileage_penalties: tuple[MileagePenaltySnapshot, ...] = field(default_factory=tuple)

    # KASKO (optional)
    kasko_rates: tuple[KaskoRateSnapshot, ...] = field(default_factory=tuple)

    # maintenance
    service_plan_ops: tuple[ServicePlanOpSnapshot, ...] = field(default_factory=tuple)
    parts_costs: tuple[PartsCostSnapshot, ...] = field(default_factory=tuple)
    labor_rates: tuple[LaborRateSnapshot, ...] = field(default_factory=tuple)

    # tyres
    tire_sizes: tuple[TireSizeSnapshot, ...] = field(default_factory=tuple)
    tire_prices: tuple[TirePriceSnapshot, ...] = field(default_factory=tuple)

    # fuel
    fuel_price_forecast: tuple[FuelPriceForecastSnapshot, ...] = field(default_factory=tuple)
    fuel_price_forecast_ru_avg: tuple[FuelPriceForecastSnapshot, ...] = field(
        default_factory=tuple,
    )
    fuel_price_forecast_ai95_region: tuple[FuelPriceForecastSnapshot, ...] = field(
        default_factory=tuple,
    )
    fuel_price_forecast_ai95_ru_avg: tuple[FuelPriceForecastSnapshot, ...] = field(
        default_factory=tuple,
    )


__all__ = ["TcoContext"]
