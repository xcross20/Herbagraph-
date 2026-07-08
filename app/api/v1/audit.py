import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.audit import AuditEventRead
from app.services.audit import list_audit_events, record_audit_event

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
async def get_audit_trail(
    patient_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventRead]:
    """Return the authenticated user's audit trail (row-level: own actions only)."""
    return await list_audit_events(db, current_user, limit=limit, patient_id=patient_id)


@router.post("/report-downloaded/{report_id}", status_code=204)
async def log_report_download(
    report_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await record_audit_event(
        db,
        action=AuditAction.REPORT_DOWNLOADED,
        summary=f"Report downloaded ({report_id})",
        user=current_user,
        resource_type="report",
        resource_id=str(report_id),
        request=request,
    )
    await db.commit()