"""Redis client — lazy init + health ping."""

from __future__ import annotations

from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

RedisClient = Redis

_redis: RedisClient | None = None


def init_redis(settings: Settings | None = None) -> RedisClient:

    global _redis
    if _redis is not None:
        return _redis

    s = settings or get_settings()
    log.info("redis.init", url=s.redis_url)
    _redis = Redis.from_url(
        s.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        log.info("redis.close")
        await _redis.aclose()
    _redis = None


def get_redis() -> RedisClient:
    if _redis is None:
        raise RuntimeError("Redis is not initialised; call init_redis() first")
    return _redis


async def check_redis() -> bool:

    redis = _redis
    if redis is None:
        return False
    try:
        pong = await redis.ping()
        return bool(pong)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis.ping_failed", error=str(exc))
        return False
