"""Backward-compat router"""

from __future__ import annotations

from fastapi import APIRouter, Header, Query

from app.api.deps import CurrentUserIdDep, ScenarioServiceDep
from app.api.schemas.scenario import (
    ScenarioCreateRequest,
    ScenarioExistsResponse,
    ScenarioListResponse,
    ScenarioRead,
)

router = APIRouter(prefix="/api/scenarios", tags=["saved-comparisons-legacy"])


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios_legacy(
    user_id: CurrentUserIdDep,
    service: ScenarioServiceDep,
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> ScenarioListResponse:
    return await service.list_scenarios(
        user_id=user_id,
        include_deleted=include_deleted,
        limit=limit,
        cursor=cursor,
    )


@router.get("/exists", response_model=ScenarioExistsResponse)
async def exists_saved_comparison_legacy(
    user_id: CurrentUserIdDep,
    service: ScenarioServiceDep,
    modification_ids: list[int] = Query(min_length=2, max_length=3),
) -> ScenarioExistsResponse:
    return await service.exists(user_id=user_id, modification_ids=modification_ids)


@router.post("", response_model=ScenarioRead, status_code=201)
async def create_scenario_legacy(
    payload: ScenarioCreateRequest,
    user_id: CurrentUserIdDep,
    service: ScenarioServiceDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ScenarioRead:
    return await service.create(
        user_id=user_id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/{scenario_id}", response_model=ScenarioRead)
async def get_scenario_legacy(
    scenario_id: str,
    user_id: CurrentUserIdDep,
    service: ScenarioServiceDep,
) -> ScenarioRead:
    return await service.get(user_id=user_id, scenario_id=scenario_id)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario_legacy(
    scenario_id: str,
    user_id: CurrentUserIdDep,
    service: ScenarioServiceDep,
) -> None:
    await service.delete(user_id=user_id, scenario_id=scenario_id)
    return None
