from __future__ import annotations

from decimal import Decimal

from app.domain.profile import StoType, UserProfile
from app.domain.tco.components.maintenance import MaintenanceComponent
from app.domain.tco.snapshots import (
    LaborRateSnapshot,
    PartsCostSnapshot,
    ServicePlanOpSnapshot,
)


def test_maintenance_basic(
    profile_balanced: UserProfile,
    service_plan_simple: tuple[ServicePlanOpSnapshot, ...],
    parts_costs_simple: tuple[PartsCostSnapshot, ...],
    labor_rates_simple: tuple[LaborRateSnapshot, ...],
) -> None:
    comp = MaintenanceComponent()
    total, breakdown = comp.compute(
        profile=profile_balanced,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=labor_rates_simple,
    )

    assert total == 29_500 + 20_000
    assert breakdown.rate_rub_per_hour == 2_000
    assert {op.operation_code for op in breakdown.operations} == {
        "oil_change",
        "tyre_swap_seasonal",
    }


def test_maintenance_swap_in_breakdown(
    profile_balanced: UserProfile,
    service_plan_simple: tuple[ServicePlanOpSnapshot, ...],
    parts_costs_simple: tuple[PartsCostSnapshot, ...],
    labor_rates_simple: tuple[LaborRateSnapshot, ...],
) -> None:
    comp = MaintenanceComponent()
    _, breakdown = comp.compute(
        profile=profile_balanced,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=labor_rates_simple,
    )
    swap = next(op for op in breakdown.operations if op.operation_code == "tyre_swap_seasonal")
    assert swap.hits == 10
    assert swap.labor_cost_rub == 2_000


def test_maintenance_dealer_more_expensive(
    profile_balanced: UserProfile,
    service_plan_simple: tuple[ServicePlanOpSnapshot, ...],
    parts_costs_simple: tuple[PartsCostSnapshot, ...],
    labor_rates_simple: tuple[LaborRateSnapshot, ...],
) -> None:
    dealer_profile = UserProfile(
        horizon_years=5,
        mileage_per_year_km=15_000,
        region_id=1,
        sto_type=StoType.DEALER,
        driver_age=35,
        driver_experience_years=10,
    )
    comp = MaintenanceComponent()
    indep_total, _ = comp.compute(
        profile=profile_balanced,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=labor_rates_simple,
    )
    dealer_total, _ = comp.compute(
        profile=dealer_profile,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=labor_rates_simple,
    )
    assert dealer_total > indep_total


def test_maintenance_fallback_rate(
    profile_balanced: UserProfile,
    service_plan_simple: tuple[ServicePlanOpSnapshot, ...],
    parts_costs_simple: tuple[PartsCostSnapshot, ...],
) -> None:
    comp = MaintenanceComponent()
    _, breakdown = comp.compute(
        profile=profile_balanced,
        service_plan_ops=service_plan_simple,
        parts_costs=parts_costs_simple,
        labor_rates=(),
    )
    assert breakdown.rate_rub_per_hour == 1_500


def test_maintenance_uses_norm_hours(profile_balanced: UserProfile) -> None:
    ops = (
        ServicePlanOpSnapshot(
            operation_id=42,
            operation_code="custom_op",
            default_norm_hours=Decimal("2.5"),
            every_km=None,
            every_months=12,
        ),
    )
    parts = (PartsCostSnapshot(operation_id=42, brand_segment="korean", avg_parts_cost_rub=0),)
    labor = (LaborRateSnapshot(region_id=1, sto_type="independent", rate_rub_per_hour=1_000),)
    comp = MaintenanceComponent()
    total, _ = comp.compute(
        profile=profile_balanced,
        service_plan_ops=ops,
        parts_costs=parts,
        labor_rates=labor,
    )
    assert total == 5 * int(Decimal("2.5") * 1_000)
