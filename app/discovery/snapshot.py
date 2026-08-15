"""Build a patient snapshot from existing labs and Discovery cases."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discovery import DiscoveryCase, DiscoveryLongitudinalSnapshot
from app.models.lab import LabReport
from app.models.patient import Patient
from app.models.patient_context import PatientContext


def snapshot_from_records(
    *,
    concerns: list[str],
    symptoms: list[str],
    labs: list[dict],
    medications: list[str],
    workup: list[str],
) -> dict:
    return {
        "current_concerns": concerns[:8],
        "symptom_history": symptoms[:16],
        "lab_trends": labs[:24],
        "medications": medications[:16],
        "other_diagnostics": workup[:12],
        "unresolved_questions": [],
    }


def prior_facts_from_snapshot(payload: dict) -> dict[str, str]:
    facts: dict[str, str] = {}
    meds = payload.get("medications") or []
    if meds:
        facts["medications"] = ", ".join(str(item) for item in meds[:6])
    for lab in payload.get("lab_trends") or []:
        name = str(lab.get("name") or "")
        if name:
            facts[f"prior lab {name}"] = str(lab.get("value") or "recorded")
    return facts


async def generate_patient_snapshot(
    db: AsyncSession, *, user_id: uuid.UUID, patient_id: uuid.UUID
) -> DiscoveryLongitudinalSnapshot:
    patient = await db.get(Patient, patient_id)
    if patient is None or patient.user_id != user_id:
        raise ValueError("Patient not found")

    cases = list(
        (
            await db.execute(
                select(DiscoveryCase)
                .where(DiscoveryCase.user_id == user_id, DiscoveryCase.patient_id == patient_id)
                .order_by(DiscoveryCase.updated_at.desc())
            )
        ).scalars()
    )
    reports = list(
        (
            await db.execute(
                select(LabReport)
                .where(LabReport.user_id == user_id, LabReport.patient_id == patient_id)
                .options(selectinload(LabReport.lab_results))
                .order_by(LabReport.created_at.desc())
                .limit(5)
            )
        ).scalars()
    )
    ctx = list(
        (
            await db.execute(select(PatientContext).where(PatientContext.patient_id == patient_id))
        ).scalars()
    )
    concerns = [case.presenting_concern for case in cases if case.presenting_concern]
    symptoms: list[str] = []
    workup: list[str] = []
    for case in cases:
        if not case.snapshot:
            continue
        try:
            raw = json.loads(case.snapshot)
        except json.JSONDecodeError:
            continue
        for item in raw.get("findings") or []:
            name = item.get("name")
            value = item.get("value")
            if not name:
                continue
            line = f"{name}: {value}" if value else str(name)
            if name in {"emg testing", "claimed normal labs", "prior_workup", "radiology report", "clinical note"}:
                workup.append(line)
            elif item.get("kind") in {"symptom", "context"}:
                symptoms.append(line)
    labs = []
    for report in reports:
        for row in report.lab_results or []:
            labs.append(
                {
                    "name": row.biomarker_name,
                    "value": row.value,
                    "status": getattr(row.status, "value", str(row.status)),
                    "collected": str(report.created_at),
                }
            )
    meds = [item.name for item in ctx if str(getattr(item.context_type, "value", item.context_type)) == "medication"]
    payload = snapshot_from_records(
        concerns=concerns, symptoms=symptoms, labs=labs, medications=meds, workup=workup
    )
    latest = (
        await db.execute(
            select(DiscoveryLongitudinalSnapshot)
            .where(DiscoveryLongitudinalSnapshot.patient_id == patient_id)
            .order_by(DiscoveryLongitudinalSnapshot.version.desc())
        )
    ).scalars().first()
    await db.execute(
        update(DiscoveryLongitudinalSnapshot)
        .where(DiscoveryLongitudinalSnapshot.patient_id == patient_id)
        .values(is_current=False)
    )
    version = 1 if latest is None else latest.version + 1
    row = DiscoveryLongitudinalSnapshot(
        user_id=user_id,
        patient_id=patient_id,
        version=version,
        is_current=True,
        payload=json.dumps(payload),
    )
    db.add(row)
    await db.flush()
    return row


async def current_snapshot(db: AsyncSession, patient_id: uuid.UUID) -> DiscoveryLongitudinalSnapshot | None:
    return (
        await db.execute(
            select(DiscoveryLongitudinalSnapshot).where(
                DiscoveryLongitudinalSnapshot.patient_id == patient_id,
                DiscoveryLongitudinalSnapshot.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
