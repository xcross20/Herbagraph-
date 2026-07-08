import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user, get_db
from app.models.user import User
from app.schemas.workspace import PatientOverviewRead, WorkspaceDashboardRead
from app.services.workspace import build_patient_overview, build_workspace_dashboard

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/dashboard", response_model=WorkspaceDashboardRead)
async def get_dashboard(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceDashboardRead:
    return await build_workspace_dashboard(db, current_user)


@router.get("/patients/{patient_id}/overview", response_model=PatientOverviewRead)
async def get_patient_overview(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> PatientOverviewRead:
    try:
        return await build_patient_overview(db, current_user, patient_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from None