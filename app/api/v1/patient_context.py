import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user, get_db
from app.models.patient import Patient
from app.models.enums import AuditAction
from app.models.patient_context import PatientContext
from app.services.audit import record_audit_event
from app.models.user import User
from app.schemas.patient_context import PatientContextCreate, PatientContextRead, PatientContextUpdate

router = APIRouter(prefix="/patients", tags=["patient-context"])


async def _get_owned_patient(patient_id: uuid.UUID, current_user: User, db: AsyncSession) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get("/{patient_id}/context", response_model=list[PatientContextRead])
async def list_patient_context(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[PatientContext]:
    await _get_owned_patient(patient_id, current_user, db)
    result = await db.execute(
        select(PatientContext)
        .where(PatientContext.patient_id == patient_id)
        .order_by(PatientContext.active.desc(), PatientContext.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{patient_id}/context", response_model=PatientContextRead, status_code=status.HTTP_201_CREATED)
async def create_patient_context(
    patient_id: uuid.UUID,
    payload: PatientContextCreate,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> PatientContext:
    await _get_owned_patient(patient_id, current_user, db)
    item = PatientContext(patient_id=patient_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit_event(
        db,
        action=AuditAction.CONTEXT_ADDED,
        summary=f"Added {payload.context_type.value}: {payload.name}",
        user=current_user,
        patient_id=patient_id,
        resource_type="patient_context",
        resource_id=str(item.id),
        request=request,
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{patient_id}/context/{context_id}", response_model=PatientContextRead)
async def update_patient_context(
    patient_id: uuid.UUID,
    context_id: uuid.UUID,
    payload: PatientContextUpdate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> PatientContext:
    await _get_owned_patient(patient_id, current_user, db)
    result = await db.execute(
        select(PatientContext).where(
            PatientContext.id == context_id, PatientContext.patient_id == patient_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{patient_id}/context/{context_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient_context(
    patient_id: uuid.UUID,
    context_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_owned_patient(patient_id, current_user, db)
    result = await db.execute(
        select(PatientContext).where(
            PatientContext.id == context_id, PatientContext.patient_id == patient_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context item not found")
    await db.delete(item)
    await db.commit()