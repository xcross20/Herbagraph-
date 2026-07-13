"""Operational status endpoints (no auth)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.config import settings
from app.database import AsyncSessionLocal

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def system_status():
    """Public readiness probe: API config + database connectivity."""
    payload = {
        "status": "ok",
        "version": __version__,
        "auth_provider": settings.auth_provider,
        "database": "unknown",
    }
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            result = await session.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'auth_provider'"
                    ")"
                )
            )
            has_auth_columns = bool(result.scalar())
        payload["database"] = "connected"
        payload["schema_ready"] = has_auth_columns
        if settings.auth_provider == "supabase" and not has_auth_columns:
            payload["status"] = "degraded"
            payload["hint"] = "Run alembic upgrade head on the linked Postgres database."
        return payload
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=503,
            content={
                **payload,
                "status": "degraded",
                "database": "unavailable",
                "detail": str(exc)[:300],
                "hint": "Link Railway Postgres and set DATABASE_URL on this service.",
            },
        )