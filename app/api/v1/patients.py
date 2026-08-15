import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_user, get_db
from app.discovery.snapshot import current_snapshot, generate_patient_snapshot
from app.models.enums import AuditAction
from app.models.patient import Patient
from app.services.audit import record_audit_event
from app.models.user import User
from app.schemas.discovery import LongitudinalSnapshotRead
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    request: Request,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    patient = Patient(
        user_id=current_user.id,
        display_name=payload.display_name,
        date_of_birth=payload.date_of_birth,
        age=payload.age,
        biological_sex=payload.biological_sex,
        notes=payload.notes,
    )
    db.add(patient)
    await db.flush()
    await record_audit_event(
        db,
        action=AuditAction.PATIENT_CREATED,
        summary=f"Patient profile created ({patient.display_name})",
        user=current_user,
        patient_id=patient.id,
        resource_type="patient",
        resource_id=str(patient.id),
        request=request,
    )
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientRead])
async def list_patients(
    current_user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)
) -> list[Patient]:
    result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id).order_by(Patient.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await db.commit()
    await db.refresh(patient)
    return patient


def _snapshot_read(row) -> LongitudinalSnapshotRead:
    try:
        payload = json.loads(row.payload)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return LongitudinalSnapshotRead(
        id=row.id,
        patient_id=row.patient_id,
        version=row.version,
        is_current=row.is_current,
        payload=payload,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _owned_patient(db: AsyncSession, patient_id: uuid.UUID, user_id: uuid.UUID) -> Patient:
    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get("/{patient_id}/longitudinal-snapshot", response_model=LongitudinalSnapshotRead)
async def get_longitudinal_snapshot(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> LongitudinalSnapshotRead:
    await _owned_patient(db, patient_id, current_user.id)
    row = await current_snapshot(db, patient_id)
    if row is None:
        try:
            row = await generate_patient_snapshot(db, user_id=current_user.id, patient_id=patient_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from exc
        await db.commit()
    return _snapshot_read(row)


@router.post("/{patient_id}/longitudinal-snapshot", response_model=LongitudinalSnapshotRead)
async def refresh_longitudinal_snapshot(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> LongitudinalSnapshotRead:
    await _owned_patient(db, patient_id, current_user.id)
    try:
        row = await generate_patient_snapshot(db, user_id=current_user.id, patient_id=patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from exc
    await db.commit()
    return _snapshot_read(row)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    await db.delete(patient)
    await db.commit()
