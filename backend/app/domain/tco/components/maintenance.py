"""Maintenance component (`C_maint`) — full scheduled service over the horizon.

This **includes** the seasonal tyre swap operation (`tyre_swap_seasonal` in
``service_plan_ops``) — the cost of the labour itself depends on region and
SBO type via ``labor_rates`` and is therefore handled here, not in the
``tyres`` component. The purchase of *new* tyre sets stays in ``C_tyres``.

Per operation in the generation's plan:

    hits = max(total_km // every_km, total_months // every_months)
    contribution = hits × (parts_cost + norm_hours × labor_rate)

When no row matches ``(region_id, sto_type)`` in ``labor_rates``, the
methodology specifies a fallback chain:

  1. Same sto_type in Moscow (region_id = 1)
  2. Hard-coded ``1500 ₽/час`` constant
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.mappings import hits_for_interval
from app.domain.tco.snapshots import (
    LaborRateSnapshot,
    PartsCostSnapshot,
    ServicePlanOpSnapshot,
)

_FALLBACK_RATE_RUB_PER_HOUR = 1500
_FALLBACK_REGION_ID = 1  # Moscow


@dataclass(frozen=True, slots=True)
class OperationContribution:
    operation_id: int
    operation_code: str
    hits: int
    parts_cost_rub: int
    labor_cost_rub: int
    total_rub: int


@dataclass(frozen=True, slots=True)
class MaintenanceBreakdown:
    rate_rub_per_hour: int
    operations: tuple[OperationContribution, ...]


def _resolve_rate(
    profile: UserProfile, labor_rates: Sequence[LaborRateSnapshot]
) -> int:
    """Find ₽/час with the 2-step fallback chain."""
    for r in labor_rates:
        if r.region_id == profile.region_id and r.sto_type == profile.sto_type.value:
            return r.rate_rub_per_hour
    for r in labor_rates:
        if r.region_id == _FALLBACK_REGION_ID and r.sto_type == profile.sto_type.value:
            return r.rate_rub_per_hour
    return _FALLBACK_RATE_RUB_PER_HOUR


class MaintenanceComponent:
    """Compute ``C_maint`` over the user's horizon (seasonal tyre swap included)."""

    def compute(
        self,
        profile: UserProfile,
        service_plan_ops: Sequence[ServicePlanOpSnapshot],
        parts_costs: Sequence[PartsCostSnapshot],
        labor_rates: Sequence[LaborRateSnapshot],
    ) -> tuple[int, MaintenanceBreakdown]:
        total_km = profile.mileage_per_year_km * profile.horizon_years
        total_months = profile.horizon_years * 12
        rate_per_hour = _resolve_rate(profile, labor_rates)

        parts_index: dict[int, int] = {
            pc.operation_id: pc.avg_parts_cost_rub for pc in parts_costs
        }

        contributions: list[OperationContribution] = []
        grand_total = 0

        for op in service_plan_ops:
            hits = hits_for_interval(
                total_km,
                total_months,
                op.every_km,
                op.every_months,
            )
            if hits == 0:
                continue
            parts = parts_index.get(op.operation_id, 0)
            labor = int((op.default_norm_hours * Decimal(rate_per_hour)).quantize(Decimal("1")))
            contrib = hits * (parts + labor)
            grand_total += contrib

            contributions.append(
                OperationContribution(
                    operation_id=op.operation_id,
                    operation_code=op.operation_code,
                    hits=hits,
                    parts_cost_rub=parts,
                    labor_cost_rub=labor,
                    total_rub=contrib,
                )
            )

        breakdown = MaintenanceBreakdown(
            rate_rub_per_hour=rate_per_hour,
            operations=tuple(contributions),
        )
        return grand_total, breakdown


__all__ = ["MaintenanceComponent", "MaintenanceBreakdown", "OperationContribution"]
