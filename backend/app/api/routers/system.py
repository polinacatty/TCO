"""System endpoints"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import PlainTextResponse

from app.api.schemas.system import LivenessResponse, ReadinessResponse, VersionResponse
from app.config import get_settings
from app.core.metrics import metrics_registry
from app.infrastructure.db import check_db
from app.infrastructure.redis_client import check_redis
from app.lifespan import AppState

router = APIRouter(tags=["system"])


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Всегда 200, пока процесс жив. Используется k8s/docker."""
    return LivenessResponse()


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    """Проверка готовности зависимостей (БД + Redis)."""
    db_ok = await check_db()
    redis_ok = await check_redis()
    state: AppState = request.app.state.app_state

    if not (db_ok and redis_ok):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if db_ok and redis_ok else "not_ready",
        db=db_ok,
        redis=redis_ok,
        startup_seconds=state.startup_seconds,
    )


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    s = get_settings()
    return VersionResponse(name=s.app_name, version=s.app_version, env=s.app_env)


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics() -> PlainTextResponse:
    """Prometheus-compatible metrics endpoint."""
    return PlainTextResponse(
        content=metrics_registry.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
