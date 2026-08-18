"""Lightweight database connectivity checks for readiness probes."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def check_database(session: AsyncSession) -> None:
    """Raise SQLAlchemyError if the database is unreachable or schema is unusable."""
    await session.execute(text("SELECT 1"))
    await session.execute(text("SELECT active FROM discovery_findings WHERE false"))