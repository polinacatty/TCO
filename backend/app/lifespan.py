"""FastAPI lifespan: init/close DB и Redis, выставление ``app.state.ready``."""

from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import FastAPI

from app.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.db import check_db, close_engine, init_engine
from app.infrastructure.redis_client import check_redis, close_redis, init_redis

log = get_logger(__name__)


@dataclass
class AppState:
    """Состояние процесса, доступное через ``request.app.state.app_state``."""

    ready: bool = False
    db_ready: bool = False
    redis_ready: bool = False
    startup_seconds: float = 0.0


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = AppState()
    app.state.app_state = state
    settings = get_settings()
    started = time.perf_counter()

    log.info("lifespan.startup", env=settings.app_env, version=settings.app_version)

    init_engine(settings)
    init_redis(settings)

    state.db_ready = await check_db()
    state.redis_ready = await check_redis()
    state.ready = state.db_ready and state.redis_ready
    state.startup_seconds = round(time.perf_counter() - started, 3)

    if not state.ready:
        log.warning(
            "lifespan.not_ready",
            db_ready=state.db_ready,
            redis_ready=state.redis_ready,
        )
    else:
        log.info("lifespan.ready", elapsed_s=state.startup_seconds)

    try:
        yield
    finally:
        log.info("lifespan.shutdown")
        await close_redis()
        await close_engine()
        state.ready = False
