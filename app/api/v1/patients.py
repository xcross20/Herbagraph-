import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientRead

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    patient = Patient(user_id=current_user.id, age=payload.age, biological_sex=payload.biological_sex)
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientRead])
async def list_patients(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Patient]:
    result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id).order_by(Patient.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
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
