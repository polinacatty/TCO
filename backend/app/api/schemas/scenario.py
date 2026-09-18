"""Schemas for /api/saved-comparisons endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    modification_ids: list[int] = Field(min_length=2, max_length=3)


class ScenarioSummaryRead(BaseModel):
    id: str
    name: str
    modifications_count: int
    modification_ids: list[int]
    created_at: datetime


class ScenarioListResponse(BaseModel):
    items: list[ScenarioSummaryRead]
    next_cursor: str | None = None
    has_more: bool = False


class ScenarioRead(BaseModel):
    id: str
    name: str
    modification_ids: list[int]
    created_at: datetime


class ScenarioExistsResponse(BaseModel):
    exists: bool
    comparison_id: str | None = None


__all__ = [
    "ScenarioCreateRequest",
    "ScenarioExistsResponse",
    "ScenarioListResponse",
    "ScenarioRead",
]
