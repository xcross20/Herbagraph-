"""Operational status endpoints (no auth)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from urllib.parse import urlparse

from app import __version__
from app.config import settings
from app.core.background_jobs import redis_reachable
from app.core.oauth import google_oauth_enabled
from app.core.privacy import encryption_key_fingerprint
from app.core.signup_access import signup_access_required
from app.core.supabase_auth import jwt_verify_mode, supabase_configured
from app.database import AsyncSessionLocal
from app.integrations.usda_fooddata import usda_configured
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ping")
async def system_ping() -> dict:
    return {"ok": True, "version": __version__}


@router.get("/status")
async def system_status():
    """Public readiness probe: API config + database connectivity."""
    payload: dict = {
        "status": "ok",
        "version": __version__,
        "auth_provider": settings.auth_provider,
        "database": "unknown",
    }
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            try:
                result = await session.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'users' AND column_name = 'auth_provider' LIMIT 1"
                    )
                )
                payload["schema_ready"] = result.first() is not None
            except Exception:
                payload["schema_ready"] = False
        payload["database"] = "connected"
        payload["encryption_configured"] = bool(settings.encryption_key.strip())
        payload["encryption_fingerprint"] = encryption_key_fingerprint()
        payload["supabase_configured"] = supabase_configured()
        payload["jwt_verify_mode"] = jwt_verify_mode()
        payload["allow_guest_auth"] = bool(settings.allow_guest_auth and settings.auth_provider == "local")
        payload["signup_access_required"] = signup_access_required()
        payload["google_oauth_enabled"] = google_oauth_enabled()
        payload["app_public_url"] = settings.app_public_url or None
        payload["usda_configured"] = usda_configured()
        redis_host = urlparse(settings.redis_url).hostname or ""
        payload["redis_host"] = redis_host or None
        payload["redis_looks_local"] = redis_host in ("localhost", "127.0.0.1", "")
        payload["redis_reachable"] = redis_reachable(celery_app)
        payload["uploads_ready"] = (
            payload.get("schema_ready")
            and payload["encryption_configured"]
            and payload["redis_reachable"]
        )
        if settings.auth_provider == "supabase" and not payload.get("supabase_configured"):
            payload["status"] = "degraded"
            payload["hint"] = (
                "AUTH_PROVIDER=supabase but SUPABASE_URL or anon/publishable key is missing."
            )
        elif settings.auth_provider == "supabase" and not payload.get("schema_ready"):
            payload["status"] = "degraded"
            payload["hint"] = "Run alembic upgrade head on the linked Postgres database."
        elif not payload["encryption_configured"]:
            payload["status"] = "degraded"
            payload["hint"] = "Set ENCRYPTION_KEY on web and worker (python scripts/generate_encryption_key.py)."
        elif payload.get("redis_looks_local"):
            payload["status"] = "degraded"
            payload["hint"] = (
                "REDIS_URL still points at localhost on the WEB service. "
                "Railway → web service → Variables → REDIS_URL → reference your Redis service."
            )
        elif not payload["redis_reachable"]:
            payload["status"] = "degraded"
            payload["hint"] = (
                f"Cannot reach Redis at {redis_host or 'unknown'}. "
                "Set REDIS_URL via variable reference on web + worker, then redeploy both."
            )
        return payload
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                **payload,
                "status": "degraded",
                "database": "unavailable",
                "error": type(exc).__name__,
                "detail": str(exc)[:300],
                "hint": "Link Railway Postgres to this web service and set DATABASE_URL.",
            },
        )