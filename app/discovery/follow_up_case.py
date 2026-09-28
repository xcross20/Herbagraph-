"""Compare the labs already on a Case with a later panel.

The later panel is another lab report. The Case keeps pointing at the first one.
No tracking row is created, and the stack verdicts are left alone.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discovery import DiscoveryCase
from app.models.enums import LabProcessingStage, LabReportStatus
from app.models.lab import LabReport
from app.models.user import User
from app.pipeline.follow_up_compare import compare_lab_rows
from app.pipeline.manual_labs import MANUAL_PATH, persist_normalized, normalize_typed_rows

async def compare_follow_up(
    db: AsyncSession,
    user: User,
    case: DiscoveryCase,
    *,
    follow_up_lab_report_id: uuid.UUID | None,
    labs: list[dict] | None,
    audience: str,
) -> dict:
    if case.lab_report_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case has no saved labs to compare.",
        )
    if follow_up_lab_report_id is not None and labs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pass a saved lab report or new values, not both.",
        )
    baseline = await _owned_report(db, user.id, case.lab_report_id)
    if baseline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
    if follow_up_lab_report_id is not None:
        if follow_up_lab_report_id == baseline.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A lab report cannot be compared with itself.",
            )
        follow = await _owned_report(db, user.id, follow_up_lab_report_id)
        if follow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab report not found")
        follow_rows = _rows(follow)
    elif labs:
        follow, follow_rows = await _write_later_panel(db, user.id, case.patient_id, labs)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a later lab value or choose a saved lab report.",
        )
    compared = compare_lab_rows(_rows(baseline), follow_rows, audience)
    if not compared["changes"] and not compared["missing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No numeric lab values could be read",
        )
    return {
        "case_id": case.id,
        "baseline_lab_report_id": baseline.id,
        "follow_up_lab_report_id": follow.id,
        **compared,
    }


async def _owned_report(db: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> LabReport | None:
    result = await db.execute(
        select(LabReport)
        .where(LabReport.id == report_id, LabReport.user_id == user_id)
        .options(selectinload(LabReport.lab_results))
    )
    return result.scalar_one_or_none()


async def _write_later_panel(
    db: AsyncSession,
    user_id: uuid.UUID,
    patient_id: uuid.UUID | None,
    labs: list[dict],
) -> tuple[LabReport, list[dict]]:
    normalized = normalize_typed_rows(labs)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No numeric lab values could be read",
        )
    report = LabReport(
        user_id=user_id,
        patient_id=patient_id,
        original_filename="manual-entry",
        encrypted_file_path=MANUAL_PATH,
        file_size_bytes=0,
        status=LabReportStatus.COMPLETE,
        processing_stage=LabProcessingStage.COMPLETE,
    )
    db.add(report)
    await db.flush()
    await persist_normalized(db, report, normalized, replace=False)
    rows = [
        {"name": row.biomarker_name, "value": row.value, "unit": row.unit}
        for row in normalized
    ]
    return report, rows


def _rows(report: LabReport) -> list[dict]:
    return [
        {"name": row.biomarker_name, "value": row.value, "unit": row.unit}
        for row in report.lab_results
    ]
