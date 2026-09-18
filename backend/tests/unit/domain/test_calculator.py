from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.profile import CarSelection, StoType, UserProfile
from app.domain.tco.calculator import TcoCalculator
from app.domain.tco.inputs import TcoContext
from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    FuelPriceForecastSnapshot,
    KaskoRateSnapshot,
    LaborRateSnapshot,
    MileagePenaltySnapshot,
    OsagoCoefficientsSnapshot,
    PartsCostSnapshot,
    ServicePlanOpSnapshot,
    TirePriceSnapshot,
    TireSizeSnapshot,
    TransportTaxRateSnapshot,
)


def _build_context(
    car: CarSnapshot,
    depreciation_rates: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
    kasko_rates: tuple[KaskoRateSnapshot, ...],
    osago_coefficients: OsagoCoefficientsSnapshot,
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...],
    service_plan_ops: tuple[ServicePlanOpSnapshot, ...],
    parts_costs: tuple[PartsCostSnapshot, ...],
    labor_rates: tuple[LaborRateSnapshot, ...],
    tire_sizes: tuple[TireSizeSnapshot, ...],
    tire_prices: tuple[TirePriceSnapshot, ...],
    fuel_forecast: tuple[FuelPriceForecastSnapshot, ...],
    start: date,
) -> TcoContext:
    return TcoContext(
        car=car,
        calculation_start_date=start,
        transport_tax_rates=transport_tax_rates,
        luxury_matches=(),
        osago_coefficients=osago_coefficients,
        depreciation_rates=depreciation_rates,
        mileage_penalties=mileage_penalties,
        kasko_rates=kasko_rates,
        service_plan_ops=service_plan_ops,
        parts_costs=parts_costs,
        labor_rates=labor_rates,
        tire_sizes=tire_sizes,
        tire_prices=tire_prices,
        fuel_price_forecast=fuel_forecast,
        fuel_price_forecast_ru_avg=(),
    )


def test_calculator_composes_all_components(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    depreciation_rates_full: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
    kasko_rates_full: tuple[KaskoRateSnapshot, ...],
    osago_coefficients: OsagoCoefficientsSnapshot,
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...],
    service_plan_simple: tuple[ServicePlanOpSnapshot, ...],
    parts_costs_simple: tuple[PartsCostSnapshot, ...],
    labor_rates_simple: tuple[LaborRateSnapshot, ...],
    tire_size_default: tuple[TireSizeSnapshot, ...],
    tire_price_default: tuple[TirePriceSnapshot, ...],
    fuel_forecast_60_months: tuple[FuelPriceForecastSnapshot, ...],
    calculation_start_date: date,
) -> None:
    context = _build_context(
        car=car_mass_c,
        depreciation_rates=depreciation_rates_full,
        mileage_penalties=mileage_penalties,
        kasko_rates=kasko_rates_full,
        osago_coefficients=osago_coefficients,
        transport_tax_rates=transport_tax_rates,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=labor_rates_simple,
        tire_sizes=tire_size_default,
        tire_prices=tire_price_default,
        fuel_forecast=fuel_forecast_60_months,
        start=calculation_start_date,
    )
    calc = TcoCalculator()
    result = calc.compute(
        profile=profile_balanced,
        selection=CarSelection(modification_id=car_mass_c.modification_id),
        context=context,
    )

    for component in (
        result.depreciation,
        result.fuel,
        result.osago,
        result.kasko,
        result.transport_tax,
        result.maintenance,
        result.tyres,
    ):
        assert component >= 0

    assert result.kasko == 0

    assert (
        result.total
        == result.depreciation
        + result.fuel
        + result.osago
        + result.kasko
        + result.transport_tax
        + result.maintenance
        + result.tyres
    )

    assert set(result.breakdowns) == {
        "depreciation",
        "fuel",
        "osago",
        "kasko",
        "transport_tax",
        "maintenance",
        "tyres",
    }


def test_calculator_kasko_increases_total(
    car_mass_c: CarSnapshot,
    depreciation_rates_full: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
    kasko_rates_full: tuple[KaskoRateSnapshot, ...],
    osago_coefficients: OsagoCoefficientsSnapshot,
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...],
    service_plan_simple: tuple[ServicePlanOpSnapshot, ...],
    parts_costs_simple: tuple[PartsCostSnapshot, ...],
    labor_rates_simple: tuple[LaborRateSnapshot, ...],
    tire_size_default: tuple[TireSizeSnapshot, ...],
    tire_price_default: tuple[TirePriceSnapshot, ...],
    fuel_forecast_60_months: tuple[FuelPriceForecastSnapshot, ...],
    calculation_start_date: date,
) -> None:
    base_profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
        driver_age=35,
        driver_experience_years=10,
        include_kasko=False,
    )
    kasko_profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
        driver_age=35,
        driver_experience_years=10,
        include_kasko=True,
    )
    context = _build_context(
        car=car_mass_c,
        depreciation_rates=depreciation_rates_full,
        mileage_penalties=mileage_penalties,
        kasko_rates=kasko_rates_full,
        osago_coefficients=osago_coefficients,
        transport_tax_rates=transport_tax_rates,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=labor_rates_simple,
        tire_sizes=tire_size_default,
        tire_prices=tire_price_default,
        fuel_forecast=fuel_forecast_60_months,
        start=calculation_start_date,
    )
    calc = TcoCalculator()
    no_kasko = calc.compute(
        profile=base_profile,
        selection=CarSelection(modification_id=car_mass_c.modification_id),
        context=context,
    )
    with_kasko = calc.compute(
        profile=kasko_profile,
        selection=CarSelection(modification_id=car_mass_c.modification_id),
        context=context,
    )
    assert with_kasko.kasko > 0
    assert with_kasko.total == no_kasko.total + with_kasko.kasko
    yearly_premium = int(
        (Decimal(1_500_000) * Decimal("4.5") / Decimal(100)).quantize(Decimal("1"))
    )
    assert with_kasko.kasko == yearly_premium * 5
