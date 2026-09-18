from __future__ import annotations

from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.components.depreciation import DepreciationComponent
from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    MileagePenaltySnapshot,
)


def test_depreciation_matches_methodology(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    depreciation_rates_full: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
) -> None:
   
    comp = DepreciationComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=depreciation_rates_full,
        penalties=mileage_penalties,
    )
    residual = Decimal(1_500_000)
    for r in (Decimal("0.85"), Decimal("0.88"), Decimal("0.90"), Decimal("0.91"), Decimal("0.92")):
        residual *= r
    residual *= Decimal("0.97")
    expected_pt = int(residual.quantize(Decimal("1")))
    assert breakdown.pt_rub == expected_pt
    assert total == 1_500_000 - expected_pt
    assert breakdown.mileage_penalty_pct == Decimal("3")


def test_depreciation_mileage_penalty_kicks_in(
    car_mass_c: CarSnapshot,
    depreciation_rates_full: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
) -> None:
    from app.domain.profile import StoType

    profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=30_000,
        region_id=1,
        sto_type=StoType.INDEPENDENT,
        driver_age=35,
        driver_experience_years=10,
    )
    comp = DepreciationComponent()
    _, breakdown = comp.compute(
        profile=profile,
        car=car_mass_c,
        rates=depreciation_rates_full,
        penalties=mileage_penalties,
    )
    assert breakdown.mileage_penalty_pct == Decimal("8")


def test_depreciation_fallback_when_missing_row(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
) -> None:
    comp = DepreciationComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=(),
        penalties=mileage_penalties,
    )
    assert total == 1_500_000 // 2
    assert breakdown.pt_rub == 1_500_000 - total
    assert breakdown.mileage_penalty_pct == Decimal("0")


def test_depreciation_uses_msrp_override(
    profile_balanced: UserProfile,
    car_mass_c: CarSnapshot,
    depreciation_rates_full: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
) -> None:
    comp = DepreciationComponent()
    _, breakdown = comp.compute(
        profile=profile_balanced,
        car=car_mass_c,
        rates=depreciation_rates_full,
        penalties=mileage_penalties,
        msrp_override_rub=2_000_000,
    )
    assert breakdown.p0_rub == 2_000_000


def test_depreciation_bucket_5_for_long_horizon(
    car_mass_c: CarSnapshot,
    depreciation_rates_full: tuple[DepreciationRateSnapshot, ...],
    mileage_penalties: tuple[MileagePenaltySnapshot, ...],
) -> None:
    from app.domain.profile import StoType

    profile = UserProfile(
        horizon_years=7,
        mileage_per_year_km=15_000,
        region_id=1,
        sto_type=StoType.INDEPENDENT,
        driver_age=35,
        driver_experience_years=10,
    )
    comp = DepreciationComponent()
    _, breakdown = comp.compute(
        profile=profile,
        car=car_mass_c,
        rates=depreciation_rates_full,
        penalties=mileage_penalties,
    )
    assert breakdown.annual_pcts[-1] == Decimal("8")
    assert breakdown.annual_pcts[-2] == Decimal("8")
