"""Simple in-process sliding-window rate limiter."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    count: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, rule: RateLimitRule) -> bool:
        now = monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - float(rule.window_seconds)
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= rule.count:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = InMemoryRateLimiter()


__all__ = ["RateLimitRule", "InMemoryRateLimiter", "rate_limiter"]
