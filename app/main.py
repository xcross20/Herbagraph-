from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.config import settings

app = FastAPI(
    title="HerbaGraph Clinical Evidence Engine",
    description="A privacy-first biomarker intelligence platform for botanicals, nutraceuticals, "
    "peptides, and longevity therapies.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": __version__}
