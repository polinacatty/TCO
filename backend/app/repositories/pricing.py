"""SQLAlchemy implementation of :class:`app.domain.ports.PricingRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.profile import UserProfile
from app.domain.tco.snapshots import (
    DepreciationRateSnapshot,
    KaskoRateSnapshot,
    LaborRateSnapshot,
    LuxuryCarSnapshot,
    MileagePenaltySnapshot,
    OsagoCoefficientsSnapshot,
    PartsCostSnapshot,
    ServicePlanOpSnapshot,
    TransportTaxRateSnapshot,
)
from app.infrastructure.orm.pricing import (
    DepreciationRate,
    KaskoRate,
    LaborRate,
    LuxuryCar,
    MileagePenalty,
    OsagoAgeExp,
    OsagoBaseTariff,
    OsagoDrivers,
    OsagoPower,
    OsagoTerritoryCoef,
    PartsCost,
    ServiceOperation,
    ServicePlanOp,
    TransportTaxRate,
)

# Categories used by OSAGO for category B passenger cars owned by private persons.
# See ml/data/seed/osago_base_tariffs.csv — vehicle_categories='B,BE', owner_type='physical'.
_OSAGO_PASSENGER_VEHICLE_CATEGORIES = "B,BE"
_OSAGO_OWNER_TYPE_PHYSICAL = "physical"
_OSAGO_POWER_FAMILY_B_BE = "B_BE"
_OSAGO_AGE_EXP_FAMILY_B_BE = "B_BE_other"


def _to_decimal(value: object) -> Decimal:
    """Coerce SQLAlchemy Numeric (Decimal | float | str) into ``Decimal``.

    SQLAlchemy returns ``Decimal`` for PostgreSQL ``NUMERIC`` but ``float`` for
    SQLite — we want a consistent type in the domain layer regardless of the
    backing store.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class SqlPricingRepository:
    """Backs ``pricing/depreciation/kasko/maintenance/osago`` lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    # Transport tax                                                       #
    # ------------------------------------------------------------------ #
    async def get_transport_tax_rates(
        self, region_id: int, vehicle_type: str = "passenger"
    ) -> Sequence[TransportTaxRateSnapshot]:
        """Fetch transport-tax rates for region + federal fallback (region_id = 0)."""
        del vehicle_type  # one-table model in MVP — kept for API symmetry
        stmt = select(TransportTaxRate).where(
            TransportTaxRate.region_id.in_([region_id, 0])
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            TransportTaxRateSnapshot(
                region_id=r.region_id,
                hp_min=int(r.hp_min),
                hp_max=int(r.hp_max),
                rate_rub_per_hp=_to_decimal(r.rate_rub_per_hp),
            )
            for r in rows
        ]

    async def find_luxury_matches(
        self, make_name: str, model_name: str, engine_volume_l: Decimal | None
    ) -> Sequence[LuxuryCarSnapshot]:
        """Loose match: same make + model substring; engine volume narrows for diesel/petrol."""
        stmt = select(LuxuryCar).where(LuxuryCar.make.ilike(make_name))
        rows = (await self._session.execute(stmt)).scalars().all()

        norm_model = model_name.lower().strip()
        out: list[LuxuryCarSnapshot] = []
        for r in rows:
            list_model = r.model.lower().strip()
            if norm_model not in list_model and list_model not in norm_model:
                continue
            if (
                engine_volume_l is not None
                and r.engine_volume_l is not None
                and abs(_to_decimal(r.engine_volume_l) - engine_volume_l) > Decimal("0.3")
            ):
                continue
            out.append(
                LuxuryCarSnapshot(
                    make_name=r.make,
                    model_name=r.model,
                    engine_type=r.engine_type,
                    engine_volume_l=(
                        _to_decimal(r.engine_volume_l) if r.engine_volume_l is not None else None
                    ),
                    price_tier_min_rub=int(r.price_tier_min_rub),
                )
            )
        return out

    # ------------------------------------------------------------------ #
    # OSAGO — pre-resolve full bundle                                     #
    # ------------------------------------------------------------------ #
    async def resolve_osago_coefficients(
        self, profile: UserProfile, power_hp: int
    ) -> OsagoCoefficientsSnapshot:
        """Resolve all seven OSAGO coefficients in one round-trip."""
        tariff_stmt = select(OsagoBaseTariff).where(
            OsagoBaseTariff.vehicle_categories == _OSAGO_PASSENGER_VEHICLE_CATEGORIES,
            OsagoBaseTariff.owner_type == _OSAGO_OWNER_TYPE_PHYSICAL,
        )
        tariff = (await self._session.execute(tariff_stmt)).scalar_one()

        kt_stmt = select(OsagoTerritoryCoef).where(
            OsagoTerritoryCoef.region_id == profile.region_id
        )
        kt_row = (await self._session.execute(kt_stmt)).scalar_one_or_none()
        if kt_row is None:
            # Federal average fallback (region_id = 0)
            kt_fallback_stmt = select(OsagoTerritoryCoef).where(
                OsagoTerritoryCoef.region_id == 0
            )
            kt_row = (await self._session.execute(kt_fallback_stmt)).scalar_one_or_none()
        kt_general = _to_decimal(kt_row.kt_general) if kt_row else Decimal("1.00")

        km_stmt = (
            select(OsagoPower)
            .where(
                OsagoPower.vehicle_family == _OSAGO_POWER_FAMILY_B_BE,
                OsagoPower.power_min_hp_excl < power_hp,
                OsagoPower.power_max_hp_incl >= power_hp,
            )
            .limit(1)
        )
        km_row = (await self._session.execute(km_stmt)).scalar_one_or_none()
        km_value = _to_decimal(km_row.km_value) if km_row else Decimal("1.00")

        kvs_stmt = (
            select(OsagoAgeExp)
            .where(
                OsagoAgeExp.vehicle_family == _OSAGO_AGE_EXP_FAMILY_B_BE,
                OsagoAgeExp.age_min_incl <= profile.driver_age,
                OsagoAgeExp.age_max_incl >= profile.driver_age,
                OsagoAgeExp.exp_min_years_incl <= profile.driver_experience_years,
                OsagoAgeExp.exp_max_years_excl > profile.driver_experience_years,
            )
            .limit(1)
        )
        kvs_row = (await self._session.execute(kvs_stmt)).scalar_one_or_none()
        kvs_value = _to_decimal(kvs_row.kvs_value) if kvs_row else Decimal("1.00")

        ko_stmt = select(OsagoDrivers).where(
            OsagoDrivers.restricted.is_(not profile.osago_unlimited_drivers),
            OsagoDrivers.owner_type == _OSAGO_OWNER_TYPE_PHYSICAL,
        )
        ko_row = (await self._session.execute(ko_stmt)).scalar_one_or_none()
        ko_value = _to_decimal(ko_row.ko_value) if ko_row else Decimal("1.00")

        return OsagoCoefficientsSnapshot(
            tb_min_rub=_to_decimal(tariff.tb_min_rub),
            tb_max_rub=_to_decimal(tariff.tb_max_rub),
            kt_general=kt_general,
            km_value=km_value,
            kvs_value=kvs_value,
            ko_value=ko_value,
        )

    # ------------------------------------------------------------------ #
    # Depreciation                                                        #
    # ------------------------------------------------------------------ #
    async def list_depreciation_rates(self) -> Sequence[DepreciationRateSnapshot]:
        rows = (await self._session.execute(select(DepreciationRate))).scalars().all()
        return [
            DepreciationRateSnapshot(
                segment_6=r.segment,
                brand_tier=r.brand_tier,
                age_year_bucket=int(r.age_year_bucket),
                annual_depreciation_pct=_to_decimal(r.annual_depreciation_pct),
            )
            for r in rows
        ]

    async def list_mileage_penalties(self) -> Sequence[MileagePenaltySnapshot]:
        rows = (await self._session.execute(select(MileagePenalty))).scalars().all()
        return [
            MileagePenaltySnapshot(
                mileage_threshold_km=int(r.mileage_threshold_km),
                extra_depreciation_pct=_to_decimal(r.extra_depreciation_pct),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # KASKO                                                               #
    # ------------------------------------------------------------------ #
    async def list_kasko_rates(self) -> Sequence[KaskoRateSnapshot]:
        rows = (await self._session.execute(select(KaskoRate))).scalars().all()
        return [
            KaskoRateSnapshot(
                brand_tier=r.brand_tier,
                segment_6=r.segment,
                age_year_bucket=int(r.age_year_bucket),
                kasko_rate_pct=_to_decimal(r.kasko_rate_pct),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Maintenance                                                         #
    # ------------------------------------------------------------------ #
    async def list_service_plan_ops(
        self, generation_id: int
    ) -> Sequence[ServicePlanOpSnapshot]:
        stmt = (
            select(ServicePlanOp, ServiceOperation.code, ServiceOperation.default_norm_hours)
            .join(ServiceOperation, ServiceOperation.id == ServicePlanOp.operation_id)
            .where(ServicePlanOp.generation_id == generation_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            ServicePlanOpSnapshot(
                operation_id=row[0].operation_id,
                operation_code=row.code,
                default_norm_hours=_to_decimal(row.default_norm_hours),
                every_km=int(row[0].every_km) if row[0].every_km is not None else None,
                every_months=int(row[0].every_months) if row[0].every_months is not None else None,
            )
            for row in rows
        ]

    async def list_parts_costs(
        self, operation_ids: Sequence[int], brand_segment: str
    ) -> Sequence[PartsCostSnapshot]:
        if not operation_ids:
            return []
        stmt = select(PartsCost).where(
            PartsCost.operation_id.in_(list(operation_ids)),
            PartsCost.brand_segment == brand_segment,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            PartsCostSnapshot(
                operation_id=int(r.operation_id),
                brand_segment=r.brand_segment,
                avg_parts_cost_rub=int(r.avg_parts_cost_rub),
            )
            for r in rows
        ]

    async def get_labor_rate(
        self, region_id: int, sto_type: str
    ) -> LaborRateSnapshot | None:
        stmt = select(LaborRate).where(
            LaborRate.region_id == region_id, LaborRate.sto_type == sto_type
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return LaborRateSnapshot(
            region_id=int(row.region_id),
            sto_type=row.sto_type,
            rate_rub_per_hour=int(row.rate_rub_per_hour),
        )


__all__ = ["SqlPricingRepository"]
