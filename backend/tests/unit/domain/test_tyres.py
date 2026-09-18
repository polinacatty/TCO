from __future__ import annotations

from app.domain.profile import StoType, UserProfile
from app.domain.tco.components.tyres import TyresComponent
from app.domain.tco.snapshots import TirePriceSnapshot, TireSizeSnapshot


def test_tyres_buys_first_winter_set_at_balanced_horizon(
    profile_balanced: UserProfile,
    tire_size_default: tuple[TireSizeSnapshot, ...],
    tire_price_default: tuple[TirePriceSnapshot, ...],
) -> None:
    comp = TyresComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        tire_sizes=tire_size_default,
        tire_prices=tire_price_default,
        segment_6="A_B",
    )
    assert breakdown.sets_purchased == 1
    assert breakdown.summer_sets_purchased == 0
    assert breakdown.winter_sets_purchased == 1
    assert breakdown.cycle_cost_rub == 20_000 + 24_000
    assert breakdown.summer_set_cost_rub == 20_000
    assert breakdown.winter_set_cost_rub == 24_000
    assert total == 24_000
    assert breakdown.yearly_amounts_rub == (24_000, 0, 0, 0, 0)


def test_tyres_low_mileage_still_buys_first_winter_set(
    tire_size_default: tuple[TireSizeSnapshot, ...],
    tire_price_default: tuple[TirePriceSnapshot, ...],
) -> None:
    profile = UserProfile(
        horizon_years=3,
        mileage_per_year_km=10_000,
        sto_type=StoType.INDEPENDENT,
    )
    comp = TyresComponent()
    total, breakdown = comp.compute(
        profile=profile,
        tire_sizes=tire_size_default,
        tire_prices=tire_price_default,
        segment_6="A_B",
    )
    assert total == 24_000
    assert breakdown.sets_purchased == 1
    assert breakdown.summer_sets_purchased == 0
    assert breakdown.winter_sets_purchased == 1
    assert breakdown.yearly_amounts_rub == (24_000, 0, 0)
    assert breakdown.size_codes == ("195/55 R16",)


def test_tyres_high_mileage_multiple_sets(
    tire_size_default: tuple[TireSizeSnapshot, ...],
    tire_price_default: tuple[TirePriceSnapshot, ...],
) -> None:
    profile = UserProfile(
        horizon_years=10,
        mileage_per_year_km=30_000,
        sto_type=StoType.INDEPENDENT,
    )
    comp = TyresComponent()
    total, breakdown = comp.compute(
        profile=profile,
        tire_sizes=tire_size_default,
        tire_prices=tire_price_default,
        segment_6="A_B",
    )
    assert breakdown.summer_km == 150_000
    assert breakdown.winter_km == 150_000
    assert breakdown.summer_sets_purchased == 2
    assert breakdown.winter_sets_purchased == 3
    assert breakdown.sets_purchased == 5
    assert total == 2 * 20_000 + 3 * 24_000
    assert breakdown.yearly_amounts_rub == (
        24_000,
        0,
        0,
        44_000,
        0,
        0,
        44_000,
        0,
        0,
        0,
    )


def test_tyres_staggered_sums_both_axles(
    profile_balanced: UserProfile,
) -> None:
    sizes = (
        TireSizeSnapshot(size_code="225/40 R19", axle="front"),
        TireSizeSnapshot(size_code="255/35 R19", axle="rear"),
    )
    prices = (
        TirePriceSnapshot(
            size_code="225/40 R19", summer_price_rub=30_000, winter_price_rub=35_000
        ),
        TirePriceSnapshot(
            size_code="255/35 R19", summer_price_rub=40_000, winter_price_rub=45_000
        ),
    )
    comp = TyresComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        tire_sizes=sizes,
        tire_prices=prices,
        segment_6="E_F",
    )
    cycle = (30_000 + 35_000) + (40_000 + 45_000)
    assert breakdown.cycle_cost_rub == cycle
    assert breakdown.summer_sets_purchased == 0
    assert breakdown.winter_sets_purchased == 1
    assert total == 35_000 + 45_000
    assert breakdown.yearly_amounts_rub == (80_000, 0, 0, 0, 0)


def test_tyres_fallback_when_no_sizes(profile_balanced: UserProfile) -> None:
    comp = TyresComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        tire_sizes=(),
        tire_prices=(),
        segment_6="A_B",
    )
    assert breakdown.size_codes == ("185/65 R15",)
    assert breakdown.winter_set_cost_rub == 18_000
    assert total == 18_000
    assert breakdown.yearly_amounts_rub == (18_000, 0, 0, 0, 0)
