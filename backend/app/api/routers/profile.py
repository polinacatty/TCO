"""Profile router"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import CurrentUserIdDep, ProfileServiceDep
from app.api.schemas.profile import ProfilePresetRequest, ProfileRead, ProfileWrite

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileRead)
async def get_profile(user_id: CurrentUserIdDep, service: ProfileServiceDep) -> ProfileRead:
    return await service.get(user_id)


@router.put("", response_model=ProfileRead)
async def put_profile(
    payload: ProfileWrite, user_id: CurrentUserIdDep, service: ProfileServiceDep
) -> ProfileRead:
    return await service.put(user_id, payload)


@router.post("/preset", response_model=ProfileRead)
async def apply_preset(
    payload: ProfilePresetRequest, user_id: CurrentUserIdDep, service: ProfileServiceDep
) -> ProfileRead:
    return await service.apply_preset(user_id, payload.preset)


@router.delete("", status_code=204)
async def delete_profile(
    user_id: CurrentUserIdDep, service: ProfileServiceDep, response: Response
) -> None:
    await service.delete(user_id)
    return None

