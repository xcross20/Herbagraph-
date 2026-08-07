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
from app.models.enums import PatientContextType
from app.schemas.patient_context import (
    PatientConditionsReplace,
    PatientContextCreate,
    PatientContextRead,
    PatientContextUpdate,
)

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


@router.put("/{patient_id}/conditions", response_model=list[PatientContextRead])
async def replace_patient_conditions(
    patient_id: uuid.UUID,
    payload: PatientConditionsReplace,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> list[PatientContext]:
    """Set the full condition matrix for a patient (toggles + Other free-text entries)."""
    await _get_owned_patient(patient_id, current_user, db)
    desired: list[str] = []
    seen: set[str] = set()
    for raw in payload.conditions or []:
        name = str(raw).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        desired.append(name)

    existing = list(
        (
            await db.execute(
                select(PatientContext).where(
                    PatientContext.patient_id == patient_id,
                    PatientContext.context_type == PatientContextType.CONDITION,
                )
            )
        )
        .scalars()
        .all()
    )
    existing_by_name = {item.name.strip().lower(): item for item in existing}
    desired_keys = {n.lower() for n in desired}

    for item in existing:
        if item.name.strip().lower() not in desired_keys:
            await db.delete(item)

    for name in desired:
        if name.lower() in existing_by_name:
            item = existing_by_name[name.lower()]
            if not item.active:
                item.active = True
            continue
        db.add(
            PatientContext(
                patient_id=patient_id,
                context_type=PatientContextType.CONDITION,
                name=name,
                active=True,
            )
        )

    await record_audit_event(
        db,
        action=AuditAction.CONTEXT_ADDED,
        summary=f"Updated condition matrix ({len(desired)} active)",
        user=current_user,
        patient_id=patient_id,
        resource_type="patient_conditions",
        resource_id=str(patient_id),
        request=request,
    )
    await db.commit()

    result = await db.execute(
        select(PatientContext)
        .where(
            PatientContext.patient_id == patient_id,
            PatientContext.context_type == PatientContextType.CONDITION,
            PatientContext.active.is_(True),
        )
        .order_by(PatientContext.name)
    )
    return list(result.scalars().all())

