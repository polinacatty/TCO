from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.components.transport_tax import TransportTaxComponent
from app.domain.tco.snapshots import (
    CarSnapshot,
    LuxuryCarSnapshot,
    TransportTaxRateSnapshot,
)


def test_transport_tax_basic(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...],
    calculation_start_date: date,
) -> None:
    comp = TransportTaxComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=transport_tax_rates,
        luxury_matches=(),
        calculation_start_date=calculation_start_date,
        year_of_manufacture=None,
    )
    assert total == 25 * 123 * 5
    assert breakdown.is_luxury is False
    assert breakdown.luxury_window_years == 0
    assert breakdown.yearly_amounts_rub == (25 * 123,) * 5


def test_transport_tax_luxury_within_window(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...],
    luxury_match_lambo: LuxuryCarSnapshot,
    calculation_start_date: date,
) -> None:
    comp = TransportTaxComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=transport_tax_rates,
        luxury_matches=(luxury_match_lambo,),
        calculation_start_date=calculation_start_date,
        year_of_manufacture=calculation_start_date.year,
    )
    yearly = 25 * 123 * 3
    assert total == yearly * 5
    assert breakdown.is_luxury is True
    assert breakdown.luxury_window_years == 20


def test_transport_tax_luxury_window_expires(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    transport_tax_rates: tuple[TransportTaxRateSnapshot, ...],
    calculation_start_date: date,
) -> None:
    lux = LuxuryCarSnapshot(
        make_name="Hyundai",
        model_name="Solaris",
        engine_type=None,
        engine_volume_l=None,
        price_tier_min_rub=10_000_000,
    )
    comp = TransportTaxComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=transport_tax_rates,
        luxury_matches=(lux,),
        calculation_start_date=calculation_start_date,
        year_of_manufacture=calculation_start_date.year - 10,
    )
    base = 25 * 123 * 5
    assert total == base
    assert breakdown.is_luxury is True


def test_transport_tax_federal_fallback(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    calculation_start_date: date,
) -> None:
    rates = (
        TransportTaxRateSnapshot(
            region_id=0,
            hp_min=100,
            hp_max=150,
            rate_rub_per_hp=Decimal("30"),
        ),
    )
    comp = TransportTaxComponent()
    total, _ = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=rates,
        luxury_matches=(),
        calculation_start_date=calculation_start_date,
        year_of_manufacture=None,
    )
    assert total == 30 * 123 * 5
