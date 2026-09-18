"""Builds a :class:`~app.domain.tco.inputs.TcoContext` from the three repositories.

This is the **boundary** between the infrastructure (async DB) and the
domain (pure, synchronous calculator). Once the context is built, the
calculator runs in plain Python — no awaits, no SQL.

We compute the calculation start date here (UTC ``today``) so the
calculator is fully deterministic for a given (profile, selection,
clock) tuple.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.domain.ports import CatalogRepository, FuelRepository, PricingRepository
from app.domain.profile import CarSelection, UserProfile
from app.domain.tco.inputs import TcoContext
from app.domain.tco.mappings import map_brand_segment


class CarNotFoundError(LookupError):
    """Raised when ``modification_id`` is not present in the catalog."""


@dataclass(frozen=True, slots=True)
class TcoContextBuilder:
    """Compose a :class:`TcoContext` from the three repositories.

    The repositories are passed in by FastAPI ``Depends`` and share a single
    :class:`sqlalchemy.ext.asyncio.AsyncSession`. We keep them as separate
    Protocol-typed attributes so unit tests can substitute in-memory stubs.
    """

    catalog: CatalogRepository
    pricing: PricingRepository
    fuel: FuelRepository

    async def build(
        self,
        profile: UserProfile,
        selection: CarSelection,
        *,
        now: datetime | None = None,
    ) -> TcoContext:
        """Eagerly load every reference row the calculator will need."""
        car = await self.catalog.get_modification(selection.modification_id)
        if car is None:
            raise CarNotFoundError(
                f"car modification {selection.modification_id} not found in catalog"
            )

        start = (now or datetime.now(UTC)).date().replace(day=1)
        horizon_months = profile.horizon_years * 12
        month_to = _add_months(start, horizon_months - 1)

        tire_sizes = await self.catalog.list_tire_sizes(car.modification_id)
        size_codes = [s.size_code for s in tire_sizes]
        tire_prices = (
            await self.catalog.list_tire_prices(size_codes) if size_codes else ()
        )

        tax_rates = await self.pricing.get_transport_tax_rates(profile.region_id)
        luxury_matches = await self.pricing.find_luxury_matches(
            car.make_name, car.model_name, car.engine_volume_l
        )
        osago = await self.pricing.resolve_osago_coefficients(profile, car.power_hp)

        depreciation_rates = await self.pricing.list_depreciation_rates()
        mileage_penalties = await self.pricing.list_mileage_penalties()
        kasko_rates = (
            await self.pricing.list_kasko_rates() if profile.include_kasko else ()
        )

        service_plan = await self.pricing.list_service_plan_ops(car.generation_id)
        operation_ids = [op.operation_id for op in service_plan]
        brand_segment = map_brand_segment(car.brand_tier, car.country)
        parts_costs = await self.pricing.list_parts_costs(operation_ids, brand_segment)
        labor_local = await self.pricing.get_labor_rate(
            profile.region_id, profile.sto_type.value
        )
        labor_moscow = await self.pricing.get_labor_rate(1, profile.sto_type.value)
        labor_rates = tuple(r for r in (labor_local, labor_moscow) if r is not None)

        fuel_type_norm = _forecast_fuel_key(car.fuel_type)
        forecast = await self.fuel.list_fuel_price_forecast(
            profile.region_id, fuel_type_norm, start, month_to
        )
        forecast_ru_avg = await self.fuel.list_fuel_price_forecast(
            0, fuel_type_norm, start, month_to
        )
        if fuel_type_norm == "ai98":
            forecast_ai95 = await self.fuel.list_fuel_price_forecast(
                profile.region_id, "ai95", start, month_to
            )
            forecast_ai95_ru_avg = await self.fuel.list_fuel_price_forecast(
                0, "ai95", start, month_to
            )
        else:
            forecast_ai95 = ()
            forecast_ai95_ru_avg = ()

        return TcoContext(
            car=car,
            calculation_start_date=start,
            transport_tax_rates=tuple(tax_rates),
            luxury_matches=tuple(luxury_matches),
            osago_coefficients=osago,
            depreciation_rates=tuple(depreciation_rates),
            mileage_penalties=tuple(mileage_penalties),
            kasko_rates=tuple(kasko_rates),
            service_plan_ops=tuple(service_plan),
            parts_costs=tuple(parts_costs),
            labor_rates=labor_rates,
            tire_sizes=tuple(tire_sizes),
            tire_prices=tuple(tire_prices),
            fuel_price_forecast=tuple(forecast),
            fuel_price_forecast_ru_avg=tuple(forecast_ru_avg),
            fuel_price_forecast_ai95_region=tuple(forecast_ai95),
            fuel_price_forecast_ai95_ru_avg=tuple(forecast_ai95_ru_avg),
        )


def _add_months(start: date, months: int) -> date:
    """Add a (possibly negative) number of months to a first-of-month date."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def _forecast_fuel_key(fuel_type: str | None) -> str:
    """Map catalog fuel values to materialised forecast keys."""
    key = (fuel_type or "AI95").upper()
    return {
        "AI92": "ai92",
        "AI95": "ai95",
        "AI98": "ai98",
        "DIESEL": "diesel",
        "HYBRID": "ai95",
    }.get(key, "ai95")


__all__ = ["TcoContextBuilder", "CarNotFoundError"]
