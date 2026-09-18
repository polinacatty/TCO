"""Favorites service."""

from __future__ import annotations

from app.api.schemas.favorites import FavoriteItemRead, FavoriteListResponse
from app.domain.ports import AuthRepository, CatalogRepository


class FavoritesService:
    def __init__(self, auth_repo: AuthRepository, catalog_repo: CatalogRepository) -> None:
        self._auth_repo = auth_repo
        self._catalog_repo = catalog_repo

    async def list_favorites(self, user_id: str) -> FavoriteListResponse:
        rows = await self._auth_repo.list_favorites(user_id)
        return FavoriteListResponse(
            items=[
                FavoriteItemRead(
                    modification_id=row.modification_id,
                    created_at=row.created_at,
                )
                for row in rows
            ]
        )

    async def add_favorite(self, *, user_id: str, modification_id: int) -> FavoriteListResponse:
        # Ignore stale IDs that are absent in catalog to keep API predictable.
        item = await self._catalog_repo.get_modification(modification_id)
        if item is not None:
            await self._auth_repo.add_favorite(user_id=user_id, modification_id=modification_id)
        return await self.list_favorites(user_id)

    async def remove_favorite(self, *, user_id: str, modification_id: int) -> FavoriteListResponse:
        await self._auth_repo.remove_favorite(user_id=user_id, modification_id=modification_id)
        return await self.list_favorites(user_id)


__all__ = ["FavoritesService"]
