from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.profile import StoType, UserProfile
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


@pytest.fixture
def profile_balanced() -> UserProfile:
    return UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        region_id=1,
        sto_type=StoType.INDEPENDENT,
        include_kasko=False,
        driver_age=35,
        driver_experience_years=10,
        osago_unlimited_drivers=False,
    )


@pytest.fixture
def car_mass_c() -> CarSnapshot:
    return CarSnapshot(
        modification_id=1,
        generation_id=1,
        model_id=1,
        make_id=1,
        make_name="Hyundai",
        model_name="Solaris",
        brand_tier="mass",
        country="South Korea",
        segment="B",
        msrp_new_rub=1_500_000,
        power_hp=123,
        engine_volume_l=Decimal("1.6"),
        fuel_type="AI95",
        fuel_consumption_combined_l_100km=Decimal("7.0"),
    )


@pytest.fixture
def depreciation_rates_full() -> tuple[DepreciationRateSnapshot, ...]:
    pcts = [Decimal("15"), Decimal("12"), Decimal("10"), Decimal("9"), Decimal("8")]
    return tuple(
        DepreciationRateSnapshot(
            segment_6="A_B",
            brand_tier="mass",
            age_year_bucket=i + 1,
            annual_depreciation_pct=p,
        )
        for i, p in enumerate(pcts)
    )


@pytest.fixture
def mileage_penalties() -> tuple[MileagePenaltySnapshot, ...]:
    return (
        MileagePenaltySnapshot(mileage_threshold_km=75_000, extra_depreciation_pct=Decimal("3")),
        MileagePenaltySnapshot(mileage_threshold_km=120_000, extra_depreciation_pct=Decimal("8")),
    )


@pytest.fixture
def kasko_rates_full() -> tuple[KaskoRateSnapshot, ...]:
    return tuple(
        KaskoRateSnapshot(
            brand_tier="mass",
            segment_6="A_B",
            age_year_bucket=i + 1,
            kasko_rate_pct=Decimal("4.5"),
        )
        for i in range(5)
    )


@pytest.fixture
def osago_coefficients() -> OsagoCoefficientsSnapshot:
    return OsagoCoefficientsSnapshot(
        tb_min_rub=Decimal("1399"),
        tb_max_rub=Decimal("8665"),
        kt_general=Decimal("1.96"),
        km_value=Decimal("1.20"),
        kvs_value=Decimal("0.95"),
        ko_value=Decimal("1.00"),
        kbm_value=Decimal("1.00"),
        ks_value=Decimal("1.00"),
    )


@pytest.fixture
def transport_tax_rates() -> tuple[TransportTaxRateSnapshot, ...]:
    """Moscow brackets, simplified."""
    return (
        TransportTaxRateSnapshot(region_id=1, hp_min=0, hp_max=100, rate_rub_per_hp=Decimal("12")),
        TransportTaxRateSnapshot(region_id=1, hp_min=100, hp_max=125, rate_rub_per_hp=Decimal("25")),
        TransportTaxRateSnapshot(region_id=1, hp_min=125, hp_max=150, rate_rub_per_hp=Decimal("35")),
        TransportTaxRateSnapshot(region_id=1, hp_min=150, hp_max=175, rate_rub_per_hp=Decimal("45")),
        TransportTaxRateSnapshot(region_id=1, hp_min=175, hp_max=200, rate_rub_per_hp=Decimal("50")),
    )


@pytest.fixture
def luxury_match_lambo() -> LuxuryCarSnapshot:
    return LuxuryCarSnapshot(
        make_name="Lamborghini",
        model_name="Urus",
        engine_type="petrol",
        engine_volume_l=Decimal("4.0"),
        price_tier_min_rub=15_000_000,
    )


@pytest.fixture
def service_plan_simple() -> tuple[ServicePlanOpSnapshot, ...]:
    return (
        ServicePlanOpSnapshot(
            operation_id=1,
            operation_code="oil_change",
            default_norm_hours=Decimal("0.7"),
            every_km=15_000,
            every_months=12,
        ),
        ServicePlanOpSnapshot(
            operation_id=2,
            operation_code="tyre_swap_seasonal",
            default_norm_hours=Decimal("1.0"),
            every_km=None,
            every_months=6,
        ),
    )


@pytest.fixture
def parts_costs_simple() -> tuple[PartsCostSnapshot, ...]:
    return (
        PartsCostSnapshot(operation_id=1, brand_segment="korean", avg_parts_cost_rub=4_500),
        PartsCostSnapshot(operation_id=2, brand_segment="korean", avg_parts_cost_rub=0),
    )


@pytest.fixture
def labor_rates_simple() -> tuple[LaborRateSnapshot, ...]:
    return (
        LaborRateSnapshot(region_id=1, sto_type="independent", rate_rub_per_hour=2_000),
        LaborRateSnapshot(region_id=1, sto_type="dealer", rate_rub_per_hour=4_500),
    )


@pytest.fixture
def tire_size_default() -> tuple[TireSizeSnapshot, ...]:
    return (TireSizeSnapshot(size_code="195/55 R16", axle="both"),)


@pytest.fixture
def tire_price_default() -> tuple[TirePriceSnapshot, ...]:
    return (
        TirePriceSnapshot(
            size_code="195/55 R16", summer_price_rub=20_000, winter_price_rub=24_000
        ),
    )


@pytest.fixture
def fuel_forecast_60_months() -> tuple[FuelPriceForecastSnapshot, ...]:
    months: list[FuelPriceForecastSnapshot] = []
    year, month = 2026, 1
    for i in range(60):
        price = Decimal("58") + Decimal("0.3") * Decimal(i)
        months.append(
            FuelPriceForecastSnapshot(
                region_id=1,
                fuel_type="ai95",
                price_month=date(year, month, 1),
                price_rub_per_l=price,
            )
        )
        month += 1
        if month > 12:
            month = 1
            year += 1
    return tuple(months)


@pytest.fixture
def calculation_start_date() -> date:
    return date(2026, 1, 1)
