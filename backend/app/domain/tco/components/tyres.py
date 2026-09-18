"""Tyres component (`C_tyres`) — **only** tyre-set purchases over the horizon.

Seasonal swap is **not** accounted for here — it lives inside the
``maintenance`` component (operation ``tyre_swap_seasonal`` in
``service_plan_ops``).

Formula:

    M_total = mileage_per_year_km × horizon_years
    M_summer = M_total / 2
    M_winter = M_total - M_summer

    N_summer = max(ceil(M_summer / TYRE_SEASON_LIFE_KM) - 1, 0)
               # factory summer tyres are included in the car purchase
    N_winter = ceil(M_winter / TYRE_SEASON_LIFE_KM)
               # the first winter set is a real post-purchase cost

    C_tyres = N_summer × Σ P_summer(size) + N_winter × Σ P_winter(size)

Staggered cars (one size on the front axle, another on the rear) sum both
sizes per set: see methodology §5.2.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.profile import UserProfile
from app.domain.tco.snapshots import TirePriceSnapshot, TireSizeSnapshot

# Resource of one seasonal tyre set, kilometres.
# Conservative value aligned with calibration baseline (§5.6).
TYRE_SET_LIFE_KM = 50_000

# Used only when a modification has no rows in ``tire_sizes``.
_FALLBACK_SUMMER_PRICE = 15_000
_FALLBACK_WINTER_PRICE = 18_000

_FALLBACK_SIZE_BY_SEGMENT6: dict[str, str] = {
    "A_B": "185/65 R15",
    "C_D": "205/55 R16",
    "E_F": "225/45 R17",
    "J_CROSS": "215/65 R17",
    "J_SUV": "265/65 R17",
    "LCV": "195/65 R15",
}


@dataclass(frozen=True, slots=True)
class TyresBreakdown:
    sets_purchased: int
    summer_sets_purchased: int
    winter_sets_purchased: int
    cycle_cost_rub: int
    summer_set_cost_rub: int
    winter_set_cost_rub: int
    total_km: int
    summer_km: int
    winter_km: int
    yearly_amounts_rub: tuple[int, ...]
    size_codes: tuple[str, ...]


def _resolve_size_codes(
    tire_sizes: Sequence[TireSizeSnapshot], segment_6: str
) -> tuple[str, ...]:
    """Return the size codes that actually wear out for this modification.

    Rules (methodology §5.2):
    * exactly one ``axle = both`` row → one size_code
    * one ``front`` + one ``rear`` row (staggered) → both sizes count
    * empty → fallback by segment_6
    """
    if not tire_sizes:
        return (_FALLBACK_SIZE_BY_SEGMENT6.get(segment_6, "205/55 R16"),)
    return tuple(s.size_code for s in tire_sizes)


def _season_costs(
    size_codes: Sequence[str], tire_prices: Sequence[TirePriceSnapshot]
) -> tuple[int, int]:
    """Return ``(summer_cost, winter_cost)`` over the selected size codes."""
    price_index = {p.size_code: p for p in tire_prices}
    summer_total = 0
    winter_total = 0
    for code in size_codes:
        entry = price_index.get(code)
        if entry is None:
            summer_total += _FALLBACK_SUMMER_PRICE
            winter_total += _FALLBACK_WINTER_PRICE
        else:
            summer_total += entry.summer_price_rub
            winter_total += entry.winter_price_rub
    return summer_total, winter_total


def _ceil_div(value: int, divisor: int) -> int:
    if value <= 0:
        return 0
    return (value + divisor - 1) // divisor


def _purchase_schedule_by_year(
    *, horizon_years: int, mileage_per_year_km: int, summer_cost: int, winter_cost: int
) -> tuple[list[int], int, int]:
    yearly = [0 for _ in range(horizon_years)]
    summer_per_year = mileage_per_year_km // 2
    winter_per_year = mileage_per_year_km - summer_per_year

    cumulative_summer = 0
    cumulative_winter = 0
    summer_bought = 0
    winter_bought = 0

    for idx in range(horizon_years):
        cumulative_summer += summer_per_year
        cumulative_winter += winter_per_year

        summer_needed = max(_ceil_div(cumulative_summer, TYRE_SET_LIFE_KM) - 1, 0)
        winter_needed = _ceil_div(cumulative_winter, TYRE_SET_LIFE_KM)

        if summer_needed > summer_bought:
            extra = summer_needed - summer_bought
            yearly[idx] += extra * summer_cost
            summer_bought = summer_needed

        if winter_needed > winter_bought:
            extra = winter_needed - winter_bought
            yearly[idx] += extra * winter_cost
            winter_bought = winter_needed

    return yearly, summer_bought, winter_bought


class TyresComponent:
    """Compute ``C_tyres`` over the user's horizon (set-wear only)."""

    def compute(
        self,
        profile: UserProfile,
        tire_sizes: Sequence[TireSizeSnapshot],
        tire_prices: Sequence[TirePriceSnapshot],
        segment_6: str,
    ) -> tuple[int, TyresBreakdown]:
        size_codes = _resolve_size_codes(tire_sizes, segment_6)
        summer_cost, winter_cost = _season_costs(size_codes, tire_prices)
        cycle_cost = summer_cost + winter_cost

        total_km = profile.mileage_per_year_km * profile.horizon_years
        summer_km = total_km // 2
        winter_km = total_km - summer_km

        yearly, summer_sets, winter_sets = _purchase_schedule_by_year(
            horizon_years=profile.horizon_years,
            mileage_per_year_km=profile.mileage_per_year_km,
            summer_cost=summer_cost,
            winter_cost=winter_cost,
        )
        n_sets = summer_sets + winter_sets

        total = sum(yearly)

        breakdown = TyresBreakdown(
            sets_purchased=n_sets,
            summer_sets_purchased=summer_sets,
            winter_sets_purchased=winter_sets,
            cycle_cost_rub=cycle_cost,
            summer_set_cost_rub=summer_cost,
            winter_set_cost_rub=winter_cost,
            total_km=total_km,
            summer_km=summer_km,
            winter_km=winter_km,
            yearly_amounts_rub=tuple(yearly),
            size_codes=size_codes,
        )
        return total, breakdown


__all__ = ["TyresComponent", "TyresBreakdown", "TYRE_SET_LIFE_KM"]
