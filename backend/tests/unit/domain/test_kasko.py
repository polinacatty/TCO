from __future__ import annotations

from decimal import Decimal

from app.domain.profile import StoType, UserProfile
from app.domain.tco.components.kasko import KaskoComponent
from app.domain.tco.snapshots import CarSnapshot, KaskoRateSnapshot


def test_kasko_disabled_returns_zero(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    kasko_rates_full: tuple[KaskoRateSnapshot, ...],
) -> None:
    comp = KaskoComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=kasko_rates_full,
    )
    assert total == 0
    assert breakdown.enabled is False


def test_kasko_enabled_uses_rate(
    car_mass_c: CarSnapshot,
    kasko_rates_full: tuple[KaskoRateSnapshot, ...],
) -> None:
    profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
        include_kasko=True,
    )
    comp = KaskoComponent()
    total, breakdown = comp.compute(
        profile=profile,
        car=car_mass_c,
        rates=kasko_rates_full,
    )
    yearly = int((Decimal(1_500_000) * Decimal("4.5") / Decimal(100)).quantize(Decimal("1")))
    assert total == yearly * 5
    assert breakdown.enabled is True
    assert all(amt == yearly for amt in breakdown.yearly_amounts_rub)


def test_kasko_falls_back_to_zero_when_no_row(
    car_mass_c: CarSnapshot,
) -> None:
    profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
        include_kasko=True,
    )
    comp = KaskoComponent()
    total, breakdown = comp.compute(profile=profile, car=car_mass_c, rates=())
    assert total == 0
    assert breakdown.enabled is True
    assert breakdown.yearly_amounts_rub == (0, 0, 0, 0, 0)
