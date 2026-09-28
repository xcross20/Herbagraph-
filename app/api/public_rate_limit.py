"""Distributed limit for unauthenticated public checks.

One process-local counter is not a limit once two workers are running.
Redis holds the counter. If Redis cannot be reached, the check refuses
rather than running unlimited.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import settings

WINDOW_S = 60
MAX_HITS = 20


class MemoryRateStore:
    """Test double. Not used in production."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def increment(self, key: str, window_s: int) -> int:
        del window_s
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class RedisRateStore:
    def __init__(self, client) -> None:
        self.client = client

    def increment(self, key: str, window_s: int) -> int:
        count = int(self.client.incr(key))
        if count == 1:
            self.client.expire(key, window_s)
        return count


def get_public_rate_store():
    import redis

    return RedisRateStore(redis.Redis.from_url(settings.redis_url, socket_timeout=1.0))


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def enforce_public_rate_limit(request: Request, store=None) -> None:
    counter = store if store is not None else get_public_rate_store()
    key = f"public-stack:{client_address(request)}"
    try:
        count = counter.increment(key, WINDOW_S)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public check is temporarily unavailable.",
        ) from exc
    if count > MAX_HITS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Slow down and try again shortly.",
        )
