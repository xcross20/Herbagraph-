from fastapi import APIRouter

from app.api.v1 import (
    analysis_sessions,
    auth,
    evidence,
    explainability,
    labs,
    patients,
    reports,
    safety,
    tracking,
    validation,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(analysis_sessions.router)
api_router.include_router(labs.router)
api_router.include_router(reports.router)
api_router.include_router(validation.router)
api_router.include_router(evidence.router)
api_router.include_router(explainability.router)
api_router.include_router(safety.router)
api_router.include_router(patients.router)
api_router.include_router(tracking.router)
