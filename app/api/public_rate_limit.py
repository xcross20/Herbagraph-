"""Shared limit for unauthenticated public checks.

The counter is one row per address in Postgres, so every API worker sees
the same count. A database failure refuses the check instead of running
unlimited. The row stores an address key and a count, never labs or medicines.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status
from sqlalchemy import case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.public_rate_bucket import PublicRateBucket

WINDOW_S = 60
MAX_HITS = 20


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


async def increment_public_bucket(db: AsyncSession, key: str, window_s: int) -> int:
    connection = await db.connection()
    dialect_name = connection.dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

    epoch = int(time.time())
    expired = PublicRateBucket.window_started_epoch < (epoch - window_s)
    stmt = dialect_insert(PublicRateBucket).values(
        bucket_key=key,
        hit_count=1,
        window_started_epoch=epoch,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[PublicRateBucket.bucket_key],
        set_={
            "hit_count": case((expired, 1), else_=PublicRateBucket.hit_count + 1),
            "window_started_epoch": case((expired, epoch), else_=PublicRateBucket.window_started_epoch),
        },
    ).returning(PublicRateBucket.hit_count)
    result = await db.execute(stmt)
    count = int(result.scalar_one())
    await db.commit()
    return count


async def enforce_public_rate_limit(request: Request, db: AsyncSession) -> None:
    key = f"public-stack:{client_address(request)}"
    try:
        count = await increment_public_bucket(db, key, WINDOW_S)
    except HTTPException:
        raise
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
