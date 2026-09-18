"""FastAPI entry-point.

Запуск::

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth as auth_router
from app.api.routers import catalog as catalog_router
from app.api.routers import favorites as favorites_router
from app.api.routers import profile as profile_router
from app.api.routers import scenario as scenario_router
from app.api.routers import scenarios_legacy as scenarios_legacy_router
from app.api.routers import system as system_router
from app.api.routers import tco as tco_router
from app.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIdMiddleware
from app.lifespan import lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()
    configure_logging(s.app_log_level, json_logs=not s.is_dev)
    log = get_logger(__name__)
    log.info("app.create", env=s.app_env, version=s.app_version)

    app = FastAPI(
        title=s.app_name,
        version=s.app_version,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    register_exception_handlers(app)

    app.include_router(system_router.router)
    app.include_router(auth_router.router)
    app.include_router(profile_router.router)
    app.include_router(favorites_router.router)
    app.include_router(scenario_router.router)
    app.include_router(scenarios_legacy_router.router)
    app.include_router(catalog_router.router)
    app.include_router(tco_router.router)

    return app


app = create_app()
