"""Catalog router"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CatalogServiceDep
from app.api.schemas.catalog import (
    GenerationRead,
    MakeRead,
    ModelRead,
    ModificationRead,
    RegionRead,
)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/regions", response_model=list[RegionRead])
async def list_regions(service: CatalogServiceDep) -> list[RegionRead]:
    """Список 85 регионов РФ для UI dropdown."""
    return await service.list_regions()


@router.get("/makes", response_model=list[MakeRead])
async def list_makes(
    service: CatalogServiceDep,
    q: str | None = Query(default=None, max_length=64, description="Substring search by make name"),
) -> list[MakeRead]:
    """Список марок"""
    return await service.list_makes(q)


@router.get("/makes/{make_id}/models", response_model=list[ModelRead])
async def list_models_by_make(
    make_id: int, service: CatalogServiceDep
) -> list[ModelRead]:
    return await service.list_models_by_make(make_id)


@router.get("/models/{model_id}/generations", response_model=list[GenerationRead])
async def list_generations_by_model(
    model_id: int, service: CatalogServiceDep
) -> list[GenerationRead]:
    return await service.list_generations_by_model(model_id)


@router.get(
    "/generations/{generation_id}/modifications",
    response_model=list[ModificationRead],
)
async def list_modifications_by_generation(
    generation_id: int, service: CatalogServiceDep
) -> list[ModificationRead]:
    return await service.list_modifications_by_generation(generation_id)


@router.get("/modifications/{modification_id}", response_model=ModificationRead)
async def get_modification(
    modification_id: int, service: CatalogServiceDep
) -> ModificationRead:
    return await service.get_modification(modification_id)
