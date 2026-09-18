"""KASKO component (`C_kasko`) — optional, controlled by ``profile.include_kasko``.

When disabled (the default in the "balanced" preset), the component returns
0 — keeping the formula structure symmetric across components without
short-circuiting at the calculator level.

    C_kasko(T) = Σ_{y=1..T}  ( kasko_rate_pct(tier, segment_6, y) / 100 × MSRP )

* The lookup falls back to ``age_year_bucket = min(y, 5)``.
* If the table has no row for ``(tier, segment_6)`` the component returns 0
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.mappings import segment_to_segment6
from app.domain.tco.snapshots import CarSnapshot, KaskoRateSnapshot

_MAX_BUCKET = 5


@dataclass(frozen=True, slots=True)
class KaskoBreakdown:
    enabled: bool
    yearly_amounts_rub: tuple[int, ...]
    yearly_rates_pct: tuple[Decimal, ...]
    msrp_rub: int


def _select_rate(
    rates: Sequence[KaskoRateSnapshot],
    brand_tier: str,
    segment_6: str,
    year: int,
) -> Decimal | None:
    bucket = min(year, _MAX_BUCKET)
    for r in rates:
        if (
            r.brand_tier == brand_tier
            and r.segment_6 == segment_6
            and r.age_year_bucket == bucket
        ):
            return r.kasko_rate_pct
    return None


class KaskoComponent:
    """Compute ``C_kasko`` when enabled, else 0."""

    def compute(
        self,
        profile: UserProfile,
        car: CarSnapshot,
        rates: Sequence[KaskoRateSnapshot],
        msrp_override_rub: int | None = None,
    ) -> tuple[int, KaskoBreakdown]:
        if not profile.include_kasko:
            return 0, KaskoBreakdown(
                enabled=False,
                yearly_amounts_rub=(),
                yearly_rates_pct=(),
                msrp_rub=car.msrp_new_rub,
            )

        msrp = msrp_override_rub if msrp_override_rub is not None else car.msrp_new_rub
        segment_6 = segment_to_segment6(car.segment)

        yearly: list[int] = []
        rates_used: list[Decimal] = []
        for y in range(1, profile.horizon_years + 1):
            rate = _select_rate(rates, car.brand_tier, segment_6, y)
            if rate is None:
                rates_used.append(Decimal("0"))
                yearly.append(0)
                continue
            premium = Decimal(msrp) * rate / Decimal(100)
            yearly.append(int(premium.quantize(Decimal("1"))))
            rates_used.append(rate)

        total = sum(yearly)
        breakdown = KaskoBreakdown(
            enabled=True,
            yearly_amounts_rub=tuple(yearly),
            yearly_rates_pct=tuple(rates_used),
            msrp_rub=msrp,
        )
        return total, breakdown


__all__ = ["KaskoComponent", "KaskoBreakdown"]
