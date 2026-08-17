import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app import __version__
from app.api.v1.router import api_router
from app.config import settings
from app.core.db_health import check_database
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

app.include_router(api_router, prefix="/api/v1")


def _runtime_environment() -> str:
    explicit = (settings.app_env or os.environ.get("HERBAGRAPH_ENV") or "").strip().lower()
    if explicit:
        return explicit
    railway = (os.environ.get("RAILWAY_ENVIRONMENT_NAME") or "").strip().lower()
    if railway:
        return railway
    return "local"


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "environment": _runtime_environment(),
    }


@app.get("/meta")
async def environment_meta() -> dict:
    """Public, non-secret runtime plane so the UI can label UAT vs production."""
    env = _runtime_environment()
    return {
        "service": "herbagraph",
        "environment": env,
        "is_production": env == "production",
        "demo_path": "/demo",
        "public_url": settings.app_public_url or "",
        "git_sha": (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:12],
        "synthetic_data_only": env != "production",
    }


@app.get("/demo")
async def demo_entry() -> RedirectResponse:
    """Human UAT entry: workspace UI on a non-production plane."""
    return RedirectResponse(url="/app.html", status_code=302)


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
