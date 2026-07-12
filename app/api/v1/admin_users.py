"""Admin user management — list, update, deactivate, delete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_db
from app.models.enums import AuditAction
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.report import RecommendationReport
from app.models.user import User
from app.schemas.admin import AdminUserDeleteResult, AdminUserListRead, AdminUserRead, AdminUserUpdate
from app.services.audit import record_audit_event

router = APIRouter(prefix="/admin", tags=["admin"])


async def _user_counts(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    if not user_ids:
        return {}

    patient_rows = await db.execute(
        select(Patient.user_id, func.count())
        .where(Patient.user_id.in_(user_ids))
        .group_by(Patient.user_id)
    )
    lab_rows = await db.execute(
        select(LabReport.user_id, func.count())
        .where(LabReport.user_id.in_(user_ids))
        .group_by(LabReport.user_id)
    )
    report_rows = await db.execute(
        select(RecommendationReport.user_id, func.count())
        .where(RecommendationReport.user_id.in_(user_ids))
        .group_by(RecommendationReport.user_id)
    )

    counts: dict[uuid.UUID, dict[str, int]] = {uid: {"patient_count": 0, "lab_report_count": 0, "report_count": 0} for uid in user_ids}
    for user_id, total in patient_rows.all():
        counts[user_id]["patient_count"] = int(total)
    for user_id, total in lab_rows.all():
        counts[user_id]["lab_report_count"] = int(total)
    for user_id, total in report_rows.all():
        counts[user_id]["report_count"] = int(total)
    return counts


def _to_admin_read(user: User, counts: dict[str, int]) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        auth_provider=user.auth_provider,
        role=user.role,
        clinic_name=user.clinic_name,
        created_at=user.created_at,
        patient_count=counts.get("patient_count", 0),
        lab_report_count=counts.get("lab_report_count", 0),
        report_count=counts.get("report_count", 0),
    )


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users", response_model=AdminUserListRead)
async def list_users(
    *,
    search: str | None = Query(None, description="Filter by email or name"),
    active_only: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListRead:
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        term = f"%{search.strip().lower()}%"
        filt = (func.lower(User.email).like(term)) | (func.lower(User.full_name).like(term))
        query = query.where(filt)
        count_query = count_query.where(filt)

    if active_only is True:
        query = query.where(User.is_active.is_(True))
        count_query = count_query.where(User.is_active.is_(True))
    elif active_only is False:
        query = query.where(User.is_active.is_(False))
        count_query = count_query.where(User.is_active.is_(False))

    total = int((await db.execute(count_query)).scalar_one())
    result = await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(limit))
    users = list(result.scalars().all())
    counts = await _user_counts(db, [u.id for u in users])

    return AdminUserListRead(
        total=total,
        items=[_to_admin_read(user, counts.get(user.id, {})) for user in users],
    )


@router.get("/users/{user_id}", response_model=AdminUserRead)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserRead:
    user = await _get_user_or_404(db, user_id)
    counts = (await _user_counts(db, [user.id])).get(user.id, {})
    return _to_admin_read(user, counts)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserRead:
    user = await _get_user_or_404(db, user_id)
    changes = payload.model_dump(exclude_unset=True)

    if user_id == admin.id and changes.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    for field, value in changes.items():
        setattr(user, field, value)

    await record_audit_event(
        db,
        action=AuditAction.USER_UPDATED,
        summary=f"Admin updated user {user.email}",
        user=admin,
        request=request,
        detail={"target_user_id": str(user.id), "changes": changes},
    )
    await db.commit()
    await db.refresh(user)
    counts = (await _user_counts(db, [user.id])).get(user.id, {})
    return _to_admin_read(user, counts)


@router.delete("/users/{user_id}", response_model=AdminUserDeleteResult)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDeleteResult:
    user = await _get_user_or_404(db, user_id)
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    email = user.email
    auth_provider = user.auth_provider
    await record_audit_event(
        db,
        action=AuditAction.USER_DELETED,
        summary=f"Admin deleted user {email}",
        user=admin,
        request=request,
        detail={"target_user_id": str(user.id), "auth_provider": auth_provider},
    )
    await db.delete(user)
    await db.commit()

    note = None
    if auth_provider == "supabase":
        note = (
            "Local HerbaGraph data removed. Supabase Auth account may still exist — "
            "delete it in the Supabase dashboard if required."
        )

    return AdminUserDeleteResult(deleted=True, user_id=user_id, email=email, note=note)