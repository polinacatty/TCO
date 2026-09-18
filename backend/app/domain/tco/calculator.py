"""TCO calculator facade — orchestrates all seven components.

Usage::

    context = await TcoContextBuilder(...).build(profile, selection)
    result = TcoCalculator().compute(profile, selection, context)

The calculator is **stateless and side-effect free**: same inputs always
produce the same :class:`TcoResult`. It is the natural unit to test
property-based: feed it controlled snapshots, compare to hand-computed
values, sweep horizons / mileages / brand_tiers.

Components used:

* :class:`DepreciationComponent`
* :class:`FuelComponent`         (monthly SARIMA sum)
* :class:`OsagoComponent`        (precise KVS from profile)
* :class:`KaskoComponent`        (optional)
* :class:`TransportTaxComponent`
* :class:`MaintenanceComponent`  (includes ``tyre_swap_seasonal``)
* :class:`TyresComponent`        (set-wear only)
"""

from __future__ import annotations

from dataclasses import asdict

from app.domain.profile import CarSelection, UserProfile
from app.domain.tco.components.depreciation import DepreciationComponent
from app.domain.tco.components.fuel import FuelComponent
from app.domain.tco.components.kasko import KaskoComponent
from app.domain.tco.components.maintenance import MaintenanceComponent
from app.domain.tco.components.osago import OsagoComponent
from app.domain.tco.components.transport_tax import TransportTaxComponent
from app.domain.tco.components.tyres import TyresComponent
from app.domain.tco.inputs import TcoContext
from app.domain.tco.mappings import segment_to_segment6
from app.domain.tco.result import ComponentBreakdown, TcoResult


class TcoCalculator:
    """Compute the full :class:`TcoResult` from a :class:`TcoContext`."""

    def __init__(
        self,
        depreciation: DepreciationComponent | None = None,
        fuel: FuelComponent | None = None,
        osago: OsagoComponent | None = None,
        kasko: KaskoComponent | None = None,
        transport_tax: TransportTaxComponent | None = None,
        maintenance: MaintenanceComponent | None = None,
        tyres: TyresComponent | None = None,
    ) -> None:
        self.depreciation = depreciation or DepreciationComponent()
        self.fuel = fuel or FuelComponent()
        self.osago = osago or OsagoComponent()
        self.kasko = kasko or KaskoComponent()
        self.transport_tax = transport_tax or TransportTaxComponent()
        self.maintenance = maintenance or MaintenanceComponent()
        self.tyres = tyres or TyresComponent()

    def compute(
        self,
        profile: UserProfile,
        selection: CarSelection,
        context: TcoContext,
    ) -> TcoResult:
        car = context.car

        dep_amount, dep_breakdown = self.depreciation.compute(
            profile=profile,
            car=car,
            rates=context.depreciation_rates,
            penalties=context.mileage_penalties,
            msrp_override_rub=selection.msrp_override_rub,
        )

        fuel_amount, fuel_breakdown = self.fuel.compute(
            profile=profile,
            car=car,
            forecast=context.fuel_price_forecast,
            forecast_ru_avg=context.fuel_price_forecast_ru_avg,
            calculation_start_date=context.calculation_start_date,
            forecast_ai95_region=context.fuel_price_forecast_ai95_region,
            forecast_ai95_ru_avg=context.fuel_price_forecast_ai95_ru_avg,
        )

        if context.osago_coefficients is None:
            raise ValueError("OSAGO coefficients must be resolved before calling compute()")
        osago_amount, osago_breakdown = self.osago.compute(
            profile=profile,
            coefficients=context.osago_coefficients,
        )

        kasko_amount, kasko_breakdown = self.kasko.compute(
            profile=profile,
            car=car,
            rates=context.kasko_rates,
            msrp_override_rub=selection.msrp_override_rub,
        )

        tax_amount, tax_breakdown = self.transport_tax.compute(
            profile=profile,
            car=car,
            rates=context.transport_tax_rates,
            luxury_matches=context.luxury_matches,
            calculation_start_date=context.calculation_start_date,
            year_of_manufacture=selection.year_of_manufacture,
        )

        maint_amount, maint_breakdown = self.maintenance.compute(
            profile=profile,
            service_plan_ops=context.service_plan_ops,
            parts_costs=context.parts_costs,
            labor_rates=context.labor_rates,
        )

        segment_6 = segment_to_segment6(car.segment)
        tyres_amount, tyres_breakdown = self.tyres.compute(
            profile=profile,
            tire_sizes=context.tire_sizes,
            tire_prices=context.tire_prices,
            segment_6=segment_6,
        )

        breakdowns = {
            "depreciation": ComponentBreakdown(details=asdict(dep_breakdown)),
            "fuel": ComponentBreakdown(details=asdict(fuel_breakdown)),
            "osago": ComponentBreakdown(details=asdict(osago_breakdown)),
            "kasko": ComponentBreakdown(details=asdict(kasko_breakdown)),
            "transport_tax": ComponentBreakdown(details=asdict(tax_breakdown)),
            "maintenance": ComponentBreakdown(details=asdict(maint_breakdown)),
            "tyres": ComponentBreakdown(details=asdict(tyres_breakdown)),
        }

        return TcoResult(
            depreciation=dep_amount,
            fuel=fuel_amount,
            osago=osago_amount,
            kasko=kasko_amount,
            transport_tax=tax_amount,
            maintenance=maint_amount,
            tyres=tyres_amount,
            breakdowns=breakdowns,
        )


__all__ = ["TcoCalculator"]
