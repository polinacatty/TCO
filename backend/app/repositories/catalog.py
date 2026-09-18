"""SQLAlchemy implementation of :class:`app.domain.ports.CatalogRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.recommendation.filters import RecommendationFilters
from app.domain.tco.snapshots import (
    CarSnapshot,
    GenerationSnapshot,
    MakeSnapshot,
    ModelSnapshot,
    ModificationListItemSnapshot,
    RegionSnapshot,
    TirePriceSnapshot,
    TireSizeSnapshot,
)
from app.infrastructure.orm.catalog import (
    CarGeneration,
    CarMake,
    CarModel,
    CarModification,
    Region,
    TireSize,
    TireSizePrice,
)


class SqlCatalogRepository:
    """Backs ``catalog.*`` reads with one SQLA session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_modification(self, modification_id: int) -> CarSnapshot | None:
        stmt = (
            select(
                CarModification,
                CarGeneration.model_id,
                CarModel.make_id,
                CarModel.segment,
                CarModel.name.label("model_name"),
                CarMake.name.label("make_name"),
                CarMake.brand_tier,
                CarMake.country,
            )
            .join(CarGeneration, CarGeneration.id == CarModification.generation_id)
            .join(CarModel, CarModel.id == CarGeneration.model_id)
            .join(CarMake, CarMake.id == CarModel.make_id)
            .where(CarModification.id == modification_id)
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None

        mod: CarModification = row[0]
        return CarSnapshot(
            modification_id=mod.id,
            generation_id=mod.generation_id,
            model_id=int(row.model_id),
            make_id=int(row.make_id),
            make_name=row.make_name,
            model_name=row.model_name,
            brand_tier=row.brand_tier,
            country=row.country,
            segment=row.segment,
            msrp_new_rub=int(mod.msrp_new_rub),
            power_hp=int(mod.power_hp),
            engine_volume_l=Decimal(str(mod.engine_volume_l)) if mod.engine_volume_l is not None else None,
            fuel_type=mod.fuel_type,
            fuel_consumption_combined_l_100km=(
                Decimal(str(mod.fuel_consumption_combined_l_100km))
                if mod.fuel_consumption_combined_l_100km is not None
                else None
            ),
        )

    async def list_tire_sizes(
        self, modification_id: int
    ) -> Sequence[TireSizeSnapshot]:
        stmt = select(TireSize).where(TireSize.modification_id == modification_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [TireSizeSnapshot(size_code=r.size_code, axle=r.axle) for r in rows]

    async def list_tire_prices(
        self, size_codes: Sequence[str]
    ) -> Sequence[TirePriceSnapshot]:
        if not size_codes:
            return []
        stmt = select(TireSizePrice).where(TireSizePrice.size_code.in_(list(size_codes)))
        rows = (await self._session.execute(stmt)).scalars().all()

        by_code: dict[str, dict[str, int]] = {}
        for r in rows:
            slot = by_code.setdefault(r.size_code, {})
            slot[r.season] = int(r.avg_set_price_rub)

        out: list[TirePriceSnapshot] = []
        for code, prices in by_code.items():
            out.append(
                TirePriceSnapshot(
                    size_code=code,
                    summer_price_rub=prices.get("summer", 0),
                    winter_price_rub=prices.get("winter", 0),
                )
            )
        return out

    # ------------------------------------------------------------------ #
    # Browse / catalog list endpoints                                     #
    # ------------------------------------------------------------------ #
    async def list_regions(self) -> Sequence[RegionSnapshot]:
        stmt = select(Region).where(Region.id > 0).order_by(Region.name.asc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            RegionSnapshot(
                id=int(r.id),
                name=r.name,
                iso_code=r.iso_code,
                federal_district=r.federal_district,
                climate_zone=r.climate_zone,
            )
            for r in rows
        ]

    async def list_makes(self, q: str | None = None) -> Sequence[MakeSnapshot]:
        stmt = select(CarMake).order_by(CarMake.name.asc())
        if q:
            stmt = stmt.where(CarMake.name_normalized.ilike(f"%{q.lower()}%"))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            MakeSnapshot(
                id=int(r.id),
                name=r.name,
                country=r.country,
                brand_tier=r.brand_tier,
            )
            for r in rows
        ]

    async def list_models_by_make(self, make_id: int) -> Sequence[ModelSnapshot]:
        stmt = (
            select(CarModel)
            .where(CarModel.make_id == make_id)
            .order_by(CarModel.name.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            ModelSnapshot(
                id=int(r.id),
                make_id=int(r.make_id),
                name=r.name,
                segment=r.segment,
                body_type=r.body_type,
            )
            for r in rows
        ]

    async def list_generations_by_model(
        self, model_id: int
    ) -> Sequence[GenerationSnapshot]:
        stmt = (
            select(CarGeneration)
            .where(CarGeneration.model_id == model_id)
            .order_by(CarGeneration.year_from.desc(), CarGeneration.name.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            GenerationSnapshot(
                id=int(r.id),
                model_id=int(r.model_id),
                name=r.name,
                year_from=int(r.year_from),
                year_to=int(r.year_to) if r.year_to is not None else None,
                restyling=int(r.restyling),
            )
            for r in rows
        ]

    async def list_modifications_by_generation(
        self, generation_id: int
    ) -> Sequence[ModificationListItemSnapshot]:
        stmt = (
            select(
                CarModification,
                CarGeneration.name.label("generation_name"),
                CarGeneration.year_from,
                CarGeneration.year_to,
                CarModel.name.label("model_name"),
                CarModel.body_type,
                CarModel.segment,
                CarMake.name.label("make_name"),
            )
            .join(CarGeneration, CarGeneration.id == CarModification.generation_id)
            .join(CarModel, CarModel.id == CarGeneration.model_id)
            .join(CarMake, CarMake.id == CarModel.make_id)
            .where(CarModification.generation_id == generation_id)
            .order_by(CarModification.power_hp.asc(), CarModification.id.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_to_list_item(row) for row in rows]

    async def get_modification_details(
        self, modification_id: int
    ) -> ModificationListItemSnapshot | None:
        stmt = (
            select(
                CarModification,
                CarGeneration.name.label("generation_name"),
                CarGeneration.year_from,
                CarGeneration.year_to,
                CarModel.name.label("model_name"),
                CarModel.body_type,
                CarModel.segment,
                CarMake.name.label("make_name"),
            )
            .join(CarGeneration, CarGeneration.id == CarModification.generation_id)
            .join(CarModel, CarModel.id == CarGeneration.model_id)
            .join(CarMake, CarMake.id == CarModel.make_id)
            .where(CarModification.id == modification_id)
        )
        row = (await self._session.execute(stmt)).one_or_none()
        return _to_list_item(row) if row is not None else None

    async def list_modifications_filtered(
        self,
        filters: RecommendationFilters,
        *,
        limit: int = 500,
    ) -> Sequence[ModificationListItemSnapshot]:
        stmt = (
            select(
                CarModification,
                CarGeneration.name.label("generation_name"),
                CarGeneration.year_from,
                CarGeneration.year_to,
                CarModel.name.label("model_name"),
                CarModel.body_type,
                CarModel.segment,
                CarMake.name.label("make_name"),
            )
            .join(CarGeneration, CarGeneration.id == CarModification.generation_id)
            .join(CarModel, CarModel.id == CarGeneration.model_id)
            .join(CarMake, CarMake.id == CarModel.make_id)
        )

        if filters.purchase_price_min_rub is not None:
            stmt = stmt.where(CarModification.msrp_new_rub >= filters.purchase_price_min_rub)
        if filters.purchase_price_max_rub is not None:
            stmt = stmt.where(CarModification.msrp_new_rub <= filters.purchase_price_max_rub)
        if filters.body_types:
            stmt = stmt.where(CarModel.body_type.in_(list(filters.body_types)))
        if filters.drives:
            stmt = stmt.where(CarModification.drive.in_(list(filters.drives)))
        if filters.fuel_types:
            stmt = stmt.where(CarModification.fuel_type.in_(list(filters.fuel_types)))
        if filters.transmissions:
            stmt = stmt.where(CarModification.transmission.in_(list(filters.transmissions)))
        if filters.segments:
            stmt = stmt.where(CarModel.segment.in_(list(filters.segments)))
        if filters.year_min is not None:
            stmt = stmt.where(CarGeneration.year_from >= filters.year_min)
        if filters.year_max is not None:
            stmt = stmt.where(CarGeneration.year_from <= filters.year_max)
        if filters.power_min_hp is not None:
            stmt = stmt.where(CarModification.power_hp >= filters.power_min_hp)
        if filters.power_max_hp is not None:
            stmt = stmt.where(CarModification.power_hp <= filters.power_max_hp)
        if filters.cargo_min_l is not None:
            stmt = stmt.where(CarModification.cargo_volume_l >= filters.cargo_min_l)
        if filters.seats_min is not None:
            stmt = stmt.where(CarModification.seats >= filters.seats_min)
        if filters.body_clearance_min_mm is not None:
            stmt = stmt.where(CarModification.body_clearance_mm >= filters.body_clearance_min_mm)

        rows = (
            await self._session.execute(
                stmt.order_by(CarModification.id.asc()).limit(limit)
            )
        ).all()
        return [_to_list_item(row) for row in rows]


def _to_list_item(row: object) -> ModificationListItemSnapshot:
    """Convert a JOIN row into a :class:`ModificationListItemSnapshot`."""
    # row[0] = CarModification; the rest are labelled.
    mod: CarModification = row[0]  # type: ignore[index]
    return ModificationListItemSnapshot(
        id=int(mod.id),
        make_name=row.make_name,  # type: ignore[attr-defined]
        model_name=row.model_name,  # type: ignore[attr-defined]
        generation_name=row.generation_name,  # type: ignore[attr-defined]
        trim_name=mod.trim_name,
        year_from=int(row.year_from),  # type: ignore[attr-defined]
        year_to=int(row.year_to) if row.year_to is not None else None,  # type: ignore[attr-defined]
        body_type=row.body_type,  # type: ignore[attr-defined]
        segment=row.segment,  # type: ignore[attr-defined]
        power_hp=int(mod.power_hp),
        engine_volume_l=Decimal(str(mod.engine_volume_l)) if mod.engine_volume_l is not None else None,
        fuel_type=mod.fuel_type,
        transmission=mod.transmission,
        drive=mod.drive,
        fuel_consumption_combined_l_100km=Decimal(str(mod.fuel_consumption_combined_l_100km)),
        msrp_new_rub=int(mod.msrp_new_rub),
        reliability_score=float(mod.reliability_score) if mod.reliability_score is not None else None,
        cargo_volume_l=int(mod.cargo_volume_l) if mod.cargo_volume_l is not None else None,
        seats=int(mod.seats) if mod.seats is not None else None,
        body_clearance_mm=int(mod.body_clearance_mm) if mod.body_clearance_mm is not None else None,
    )


__all__ = ["SqlCatalogRepository"]
