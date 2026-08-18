import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app import __version__
from app.api.v1.router import api_router
from app.config import settings
from app.core.db_health import check_database
from app.core.runtime_env import runtime_environment
from app.database import AsyncSessionLocal

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="HerbaGraph Clinical Evidence Engine",
    description="A privacy-first biomarker intelligence platform for botanicals, nutraceuticals, "
    "peptides, and longevity therapies.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from app.discovery.observability import correlation_id

        request_id = request.headers.get("x-request-id") or correlation_id()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


app.add_middleware(CorrelationIdMiddleware)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "environment": runtime_environment(),
    }


@app.get("/meta")
async def environment_meta() -> dict:
    """Public, non-secret runtime plane so the UI can label UAT vs production."""
    env = runtime_environment()
    from app.discovery.dark_launch import truth_layer_is_authoritative
    from app.discovery.telemetry import snapshot

    return {
        "service": "herbagraph",
        "environment": env,
        "is_production": env == "production",
        "demo_path": "/demo",
        "public_url": settings.app_public_url or "",
        "git_sha": (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:12],
        "synthetic_data_only": env != "production",
        "truth_layer_authoritative": truth_layer_is_authoritative(),
        "tripwires": snapshot(),
    }


@app.get("/demo")
async def demo_entry() -> RedirectResponse:
    """Human UAT entry: landing page with links into the live UI."""
    return RedirectResponse(url="/demo.html", status_code=302)


@app.get("/ready")
async def readiness_check() -> dict:
    """Verify the API can reach Postgres (migrations should run on container start)."""
    try:
        async with AsyncSessionLocal() as session:
            await check_database(session)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable ({type(exc).__name__}). Check DATABASE_URL and run alembic upgrade head.",
        ) from exc
    return {"status": "ok", "database": "connected", "version": __version__}


@app.get("/")
async def root_redirect() -> RedirectResponse:
    """Public marketing homepage — sign-in lives at /login.html, workspace at /app.html."""
    return RedirectResponse(url="/index.html", status_code=302)


# Serves the bare-bones frontend (frontend/index.html) at "/". Mounted last so it
# never shadows the API routes registered above.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
