"""Async SQLAlchemy engine + session factory"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    s = settings or get_settings()
    log.info(
        "db.init",
        pool_size=s.database_pool_size,
        max_overflow=s.database_max_overflow,
    )

    _engine = create_async_engine(
        s.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=s.database_pool_size,
        max_overflow=s.database_max_overflow,
        future=True,
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )
    return _engine


async def close_engine() -> None:
    
    global _engine, _session_factory
    if _engine is not None:
        log.info("db.close")
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB engine is not initialised; call init_engine() first")
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:

    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_db() -> bool:

    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health-check логирует и идёт дальше
        log.warning("db.ping_failed", error=str(exc))
        return False
