"""CatalogService — orchestrates :class:`CatalogRepository` reads."""

from __future__ import annotations

from app.api.schemas.catalog import (
    GenerationRead,
    MakeRead,
    ModelRead,
    ModificationRead,
    RegionRead,
)
from app.core.exceptions import NotFoundError
from app.domain.ports import CatalogRepository
from app.domain.tco.snapshots import ModificationListItemSnapshot


class CatalogService:
    """Read-only orchestration over :class:`CatalogRepository`."""

    def __init__(self, repository: CatalogRepository) -> None:
        self._repo = repository

    # ----- regions -------------------------------------------------------- #
    async def list_regions(self) -> list[RegionRead]:
        rows = await self._repo.list_regions()
        return [RegionRead.model_validate(r, from_attributes=True) for r in rows]

    # ----- makes / models / generations / modifications -------------------- #
    async def list_makes(self, q: str | None = None) -> list[MakeRead]:
        rows = await self._repo.list_makes(q)
        return [MakeRead.model_validate(r, from_attributes=True) for r in rows]

    async def list_models_by_make(self, make_id: int) -> list[ModelRead]:
        rows = await self._repo.list_models_by_make(make_id)
        if not rows:
            # Differentiate between an unknown make and a make with no models:
            # for MVP we treat both as 404 since the navigation hierarchy is
            # strictly ordered.
            raise NotFoundError(f"no models for make_id={make_id}")
        return [ModelRead.model_validate(r, from_attributes=True) for r in rows]

    async def list_generations_by_model(self, model_id: int) -> list[GenerationRead]:
        rows = await self._repo.list_generations_by_model(model_id)
        if not rows:
            raise NotFoundError(f"no generations for model_id={model_id}")
        return [GenerationRead.model_validate(r, from_attributes=True) for r in rows]

    async def list_modifications_by_generation(
        self, generation_id: int
    ) -> list[ModificationRead]:
        rows = await self._repo.list_modifications_by_generation(generation_id)
        if not rows:
            raise NotFoundError(
                f"no modifications for generation_id={generation_id}"
            )
        return [_to_modification_read(r) for r in rows]

    async def get_modification(self, modification_id: int) -> ModificationRead:
        row = await self._repo.get_modification_details(modification_id)
        if row is None:
            raise NotFoundError(f"modification {modification_id} not found")
        return _to_modification_read(row)


def _to_modification_read(snapshot: ModificationListItemSnapshot) -> ModificationRead:
    """Convert internal snapshot → external Pydantic DTO."""
    return ModificationRead(
        id=snapshot.id,
        make=snapshot.make_name,
        model=snapshot.model_name,
        generation=snapshot.generation_name,
        trim_name=snapshot.trim_name,
        year_from=snapshot.year_from,
        year_to=snapshot.year_to,
        body_type=snapshot.body_type,
        segment=snapshot.segment,
        power_hp=snapshot.power_hp,
        engine_volume_l=float(snapshot.engine_volume_l) if snapshot.engine_volume_l else None,
        fuel_type=snapshot.fuel_type,
        transmission=snapshot.transmission,
        drive=snapshot.drive,
        fuel_consumption_combined_l_100km=float(snapshot.fuel_consumption_combined_l_100km),
        msrp_new_rub=snapshot.msrp_new_rub,
    )


__all__ = ["CatalogService"]
