"""SQLAlchemy implementation of :class:`app.domain.ports.FuelRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tco.snapshots import FuelPriceForecastSnapshot
from app.infrastructure.orm.pricing import FuelPriceForecast


class SqlFuelRepository:
    """Backs reads from the materialised SARIMA forecast table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_fuel_price_forecast(
        self,
        region_id: int,
        fuel_type: str,
        month_from: date,
        month_to: date,
    ) -> Sequence[FuelPriceForecastSnapshot]:
        stmt = (
            select(FuelPriceForecast)
            .where(
                FuelPriceForecast.region_id == region_id,
                FuelPriceForecast.fuel_type == fuel_type,
                FuelPriceForecast.price_month >= month_from,
                FuelPriceForecast.price_month <= month_to,
            )
            .order_by(FuelPriceForecast.price_month.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        from decimal import Decimal

        return [
            FuelPriceForecastSnapshot(
                region_id=int(r.region_id),
                fuel_type=r.fuel_type,
                price_month=r.price_month,
                price_rub_per_l=(
                    r.price_rub_per_l
                    if isinstance(r.price_rub_per_l, Decimal)
                    else Decimal(str(r.price_rub_per_l))
                ),
            )
            for r in rows
        ]


__all__ = ["SqlFuelRepository"]
