"""Depreciation component (`C_dep`) — capital loss over the horizon.

Implements the parametric model from ADR-0001 (rejecting an ML model on
50 k+ used-listings in favour of an explicit, defensible coefficient table):

    P_T = P₀ × ∏_{y=1..T} (1 − r_y / 100) × (1 − mileage_penalty / 100)
    C_dep = P₀ − round(P_T)

* ``r_y`` is ``annual_depreciation_pct`` for bucket ``min(y, 5)`` from
  ``depreciation_rates`` for the matching ``(segment_6, brand_tier)`` pair.
* ``mileage_penalty`` is the largest threshold that ``mileage_per_year_km ×
  horizon`` crosses in ``mileage_penalties`` (§9.7 — one penalty, not
  cumulative).
* Fallback if no ``(segment_6, brand_tier)`` row exists: ``C_dep = P₀ // 2``
  (50 % over the horizon.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.mappings import segment_to_segment6
from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    MileagePenaltySnapshot,
)

_MAX_BUCKET = 5  # "5+" plateau


@dataclass(frozen=True, slots=True)
class DepreciationBreakdown:
    p0_rub: int
    pt_rub: int
    annual_pcts: tuple[Decimal, ...]
    mileage_penalty_pct: Decimal
    segment_6: str
    brand_tier: str


def _select_rate(
    rates: Sequence[DepreciationRateSnapshot],
    segment_6: str,
    brand_tier: str,
    year: int,
) -> Decimal | None:
    """Look up annual_depreciation_pct for (segment_6, brand_tier, age bucket)."""
    bucket = min(year, _MAX_BUCKET)
    for r in rates:
        if (
            r.segment_6 == segment_6
            and r.brand_tier == brand_tier
            and r.age_year_bucket == bucket
        ):
            return r.annual_depreciation_pct
    return None


def _resolve_mileage_penalty(
    total_km: int, penalties: Sequence[MileagePenaltySnapshot]
) -> Decimal:
    """Take the *highest* crossed threshold."""
    crossed = [p for p in penalties if total_km >= p.mileage_threshold_km]
    if not crossed:
        return Decimal("0")
    return max(p.extra_depreciation_pct for p in crossed)


class DepreciationComponent:
    """Compute ``C_dep`` for the given car + profile."""

    def compute(
        self,
        profile: UserProfile,
        car: CarSnapshot,
        rates: Sequence[DepreciationRateSnapshot],
        penalties: Sequence[MileagePenaltySnapshot],
        msrp_override_rub: int | None = None,
    ) -> tuple[int, DepreciationBreakdown]:
        p0 = msrp_override_rub if msrp_override_rub is not None else car.msrp_new_rub
        segment_6 = segment_to_segment6(car.segment)

        # ---- collect r_y for every year of the horizon ----------------------
        annual_pcts: list[Decimal] = []
        any_missing = False
        for y in range(1, profile.horizon_years + 1):
            r = _select_rate(rates, segment_6, car.brand_tier, y)
            if r is None:
                any_missing = True
                annual_pcts.append(Decimal("0"))
            else:
                annual_pcts.append(r)

        if any_missing:
            # Methodology §9.2 fallback — 50 % over the horizon.
            half = p0 // 2
            return half, DepreciationBreakdown(
                p0_rub=p0,
                pt_rub=p0 - half,
                annual_pcts=tuple(annual_pcts),
                mileage_penalty_pct=Decimal("0"),
                segment_6=segment_6,
                brand_tier=car.brand_tier,
            )

        # ---- compute P_T ----------------------------------------------------
        total_km = profile.mileage_per_year_km * profile.horizon_years
        mileage_penalty = _resolve_mileage_penalty(total_km, penalties)

        residual = Decimal(p0)
        for r in annual_pcts:
            residual *= Decimal(1) - r / Decimal(100)
        residual *= Decimal(1) - mileage_penalty / Decimal(100)
        pt = int(residual.quantize(Decimal("1")))

        c_dep = p0 - pt
        breakdown = DepreciationBreakdown(
            p0_rub=p0,
            pt_rub=pt,
            annual_pcts=tuple(annual_pcts),
            mileage_penalty_pct=mileage_penalty,
            segment_6=segment_6,
            brand_tier=car.brand_tier,
        )
        return c_dep, breakdown


__all__ = ["DepreciationComponent", "DepreciationBreakdown"]
