"""Transport tax component (`C_tax`).

Implements ст. 358-363 НК РФ + перечень Минпромторга luxury bracket.

Formula (per tax year ``Y`` in the horizon):

    C_tax(Y) = N_hp × τ(region_id, hp_bracket) × k_lux(Y)

Sum is taken over T tax years starting at ``calculation_start_date.year``.
``k_lux`` is 3 if the modification appears in ``luxury_car_list`` and the
year is within the legal window (10 years for the 10–15 M ₽ bracket, 20 for
the 15+ M ₽ bracket); otherwise 1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.snapshots import (
    CarSnapshot,
    LuxuryCarSnapshot,
    TransportTaxRateSnapshot,
)

_LUX_WINDOW_10_15M = 10  # years
_LUX_WINDOW_15M = 20  # years


@dataclass(frozen=True, slots=True)
class TransportTaxBreakdown:
    """Per-year tax decomposition surfaced to the API for transparency."""

    yearly_amounts_rub: tuple[int, ...]
    rate_rub_per_hp: int
    is_luxury: bool
    luxury_window_years: int  # 0 if not luxury


def _select_rate(
    rates: Sequence[TransportTaxRateSnapshot],
    region_id: int,
    power_hp: int,
) -> Decimal:
    """Find the rate row matching (region, hp bracket), with federal fallback."""
    for r in rates:
        if r.region_id == region_id and r.hp_min <= power_hp <= r.hp_max:
            return r.rate_rub_per_hp
    # Federal fallback (region_id = 0)
    for r in rates:
        if r.region_id == 0 and r.hp_min <= power_hp <= r.hp_max:
            return r.rate_rub_per_hp
    return Decimal("0")


def _luxury_window(luxury_matches: Sequence[LuxuryCarSnapshot]) -> int:
    """Return the maximum legal "increased tax" window (in years) over all matches.

    Per ст. 362 НК РФ:
    * 10 years for 10..15 M ₽ bracket
    * 20 years for 15+ M ₽ bracket
    """
    window = 0
    for lux in luxury_matches:
        if lux.price_tier_min_rub >= 15_000_000:
            window = max(window, _LUX_WINDOW_15M)
        elif lux.price_tier_min_rub >= 10_000_000:
            window = max(window, _LUX_WINDOW_10_15M)
    return window


class TransportTaxComponent:
    """Compute ``C_tax`` over the user's horizon."""

    def compute(
        self,
        profile: UserProfile,
        car: CarSnapshot,
        rates: Sequence[TransportTaxRateSnapshot],
        luxury_matches: Sequence[LuxuryCarSnapshot],
        calculation_start_date: date,
        year_of_manufacture: int | None,
    ) -> tuple[int, TransportTaxBreakdown]:
        rate = _select_rate(rates, profile.region_id, car.power_hp)
        per_hp = int(rate * car.power_hp)

        luxury_window = _luxury_window(luxury_matches)
        is_luxury = luxury_window > 0
        year_base = year_of_manufacture or calculation_start_date.year
        lux_until = year_base + luxury_window - 1 if is_luxury else 0

        yearly: list[int] = []
        for offset in range(profile.horizon_years):
            tax_year = calculation_start_date.year + offset
            k_lux = 3 if is_luxury and year_base <= tax_year <= lux_until else 1
            yearly.append(per_hp * k_lux)

        total = sum(yearly)
        breakdown = TransportTaxBreakdown(
            yearly_amounts_rub=tuple(yearly),
            rate_rub_per_hp=per_hp,
            is_luxury=is_luxury,
            luxury_window_years=luxury_window,
        )
        return total, breakdown


__all__ = ["TransportTaxComponent", "TransportTaxBreakdown"]
