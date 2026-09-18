from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.profile import StoType, UserProfile
from app.domain.tco.components.fuel import EV_PRICE_RUB_PER_KWH, FuelComponent
from app.domain.tco.snapshots import CarSnapshot, FuelPriceForecastSnapshot


def test_fuel_uses_forecast_monthly(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    fuel_forecast_60_months: tuple[FuelPriceForecastSnapshot, ...],
    calculation_start_date: date,
) -> None:
    comp = FuelComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        forecast=fuel_forecast_60_months,
        forecast_ru_avg=(),
        calculation_start_date=calculation_start_date,
    )
    monthly_l = Decimal("7.0") * Decimal(15_000) / Decimal(12) / Decimal(100)
    expected = sum(monthly_l * r.price_rub_per_l for r in fuel_forecast_60_months)
    assert total == int(expected.quantize(Decimal("1")))
    assert breakdown.used_default_constant is False
    assert breakdown.used_ru_avg_fallback is False
    assert breakdown.months == 60
    assert len(breakdown.yearly_amounts_rub) == 5
    assert sum(breakdown.yearly_amounts_rub) == total
    assert breakdown.yearly_amounts_rub[-1] > breakdown.yearly_amounts_rub[0]


def test_fuel_falls_back_to_ru_avg(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    fuel_forecast_60_months: tuple[FuelPriceForecastSnapshot, ...],
    calculation_start_date: date,
) -> None:
    ru_avg = tuple(
        FuelPriceForecastSnapshot(
            region_id=0,
            fuel_type=r.fuel_type,
            price_month=r.price_month,
            price_rub_per_l=r.price_rub_per_l,
        )
        for r in fuel_forecast_60_months
    )
    comp = FuelComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        forecast=(),
        forecast_ru_avg=ru_avg,
        calculation_start_date=calculation_start_date,
    )
    assert total > 0
    assert breakdown.used_ru_avg_fallback is True


def test_fuel_electric_uses_flat_tariff(
    profile_balanced: UserProfile,
    calculation_start_date: date,
) -> None:
    car = CarSnapshot(
        modification_id=99,
        generation_id=99,
        model_id=99,
        make_id=99,
        make_name="Tesla",
        model_name="Model Y",
        brand_tier="premium",
        country="USA",
        segment="J_CROSS",
        msrp_new_rub=8_000_000,
        power_hp=384,
        engine_volume_l=None,
        fuel_type="ELECTRIC",
        fuel_consumption_combined_l_100km=Decimal("18.0"),  # kWh / 100 km
    )
    comp = FuelComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car,
        forecast=(),
        forecast_ru_avg=(),
        calculation_start_date=calculation_start_date,
    )
    kwh = Decimal("18.0") * Decimal(15_000) / Decimal(100) * Decimal(5)
    assert total == int((kwh * EV_PRICE_RUB_PER_KWH).quantize(Decimal("1")))
    assert breakdown.fuel_type == "ELECTRIC"
    assert breakdown.yearly_amounts_rub == (17_550,) * 5


def test_fuel_hybrid_applies_consumption_factor(
    fuel_forecast_60_months: tuple[FuelPriceForecastSnapshot, ...],
    calculation_start_date: date,
) -> None:
    car = CarSnapshot(
        modification_id=99,
        generation_id=99,
        model_id=99,
        make_id=99,
        make_name="Toyota",
        model_name="Camry Hybrid",
        brand_tier="japanese_korean_mass",
        country="Japan",
        segment="D",
        msrp_new_rub=4_500_000,
        power_hp=178,
        engine_volume_l=Decimal("2.5"),
        fuel_type="HYBRID",
        fuel_consumption_combined_l_100km=Decimal("5.5"),
    )
    profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
        driver_age=35,
        driver_experience_years=10,
    )
    comp = FuelComponent()
    total, breakdown = comp.compute(
        profile=profile,
        car=car,
        forecast=fuel_forecast_60_months,
        forecast_ru_avg=(),
        calculation_start_date=calculation_start_date,
    )
    assert breakdown.consumption_l_per_100km == Decimal("5.5") * Decimal("0.85")
    assert total > 0


def test_fuel_ai98_uses_ai95_forecast_when_ai98_missing(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    fuel_forecast_60_months: tuple[FuelPriceForecastSnapshot, ...],
    calculation_start_date: date,
) -> None:
    car = CarSnapshot(
        modification_id=car_mass_c.modification_id,
        generation_id=car_mass_c.generation_id,
        model_id=car_mass_c.model_id,
        make_id=car_mass_c.make_id,
        make_name=car_mass_c.make_name,
        model_name=car_mass_c.model_name,
        brand_tier=car_mass_c.brand_tier,
        country=car_mass_c.country,
        segment=car_mass_c.segment,
        msrp_new_rub=car_mass_c.msrp_new_rub,
        power_hp=car_mass_c.power_hp,
        engine_volume_l=car_mass_c.engine_volume_l,
        fuel_type="AI98",
        fuel_consumption_combined_l_100km=car_mass_c.fuel_consumption_combined_l_100km,
    )
    comp = FuelComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car,
        forecast=(),
        forecast_ru_avg=(),
        calculation_start_date=calculation_start_date,
        forecast_ai95_region=fuel_forecast_60_months,
    )
    assert total > 0
    assert breakdown.used_ai98_from_ai95 is True
    assert breakdown.used_default_constant is False
    assert breakdown.yearly_amounts_rub[-1] > breakdown.yearly_amounts_rub[0]
