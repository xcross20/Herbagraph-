from fastapi import APIRouter

from app.api.v1 import auth, evidence, labs, patients, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(labs.router)
api_router.include_router(reports.router)
api_router.include_router(evidence.router)
api_router.include_router(patients.router)
