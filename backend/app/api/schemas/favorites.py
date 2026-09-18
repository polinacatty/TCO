"""Schemas for favorites endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FavoriteAddRequest(BaseModel):
    modification_id: int = Field(ge=1)


class FavoriteItemRead(BaseModel):
    modification_id: int
    created_at: datetime


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItemRead]


__all__ = ["FavoriteAddRequest", "FavoriteItemRead", "FavoriteListResponse"]
