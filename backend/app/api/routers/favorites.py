"""Favorites router"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserIdDep, FavoritesServiceDep
from app.api.schemas.favorites import FavoriteAddRequest, FavoriteListResponse

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    user_id: CurrentUserIdDep,
    service: FavoritesServiceDep,
) -> FavoriteListResponse:
    return await service.list_favorites(user_id)


@router.post("", response_model=FavoriteListResponse)
async def add_favorite(
    payload: FavoriteAddRequest,
    user_id: CurrentUserIdDep,
    service: FavoritesServiceDep,
) -> FavoriteListResponse:
    return await service.add_favorite(user_id=user_id, modification_id=payload.modification_id)


@router.delete("/{modification_id}", response_model=FavoriteListResponse)
async def remove_favorite(
    modification_id: int,
    user_id: CurrentUserIdDep,
    service: FavoritesServiceDep,
) -> FavoriteListResponse:
    return await service.remove_favorite(user_id=user_id, modification_id=modification_id)
