"""Pydantic schemas для system-эндпоинтов."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: str = Field(default="alive")


class ReadinessResponse(BaseModel):
    status: str = Field(description="ready | not_ready")
    db: bool
    redis: bool
    startup_seconds: float


class VersionResponse(BaseModel):
    name: str
    version: str
    env: str
