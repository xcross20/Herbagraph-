"""Typed lab entry — same normalizer as parsed PDFs."""

from __future__ import annotations

from app.models.enums import LabProcessingStage, LabReportStatus
from app.models.lab import LabReport, LabResult
from app.pipeline.biomarker_normalizer import canonical_name_for_persist, normalize_lab_results
from app.schemas.pipeline import ParsedLabResult

MANUAL_PATH = "manual://"


def is_manual_report(lab_report: LabReport) -> bool:
    return (lab_report.encrypted_file_path or "").startswith(MANUAL_PATH)


def normalize_typed_rows(rows: list[dict], *, sex: str | None = None):
    parsed: list[ParsedLabResult] = []
    for row in rows:
        name = str(row.get("name") or row.get("biomarker_name") or row.get("raw_test_name") or "").strip()
        if not name:
            continue
        try:
            value = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        parsed.append(
            ParsedLabResult(
                raw_test_name=name,
                value=value,
                unit=row.get("unit"),
                reference_range_low=row.get("reference_range_low"),
                reference_range_high=row.get("reference_range_high"),
                parser_pattern="manual",
                parse_confidence=1.0,
            )
        )
    return normalize_lab_results(parsed, sex=sex)


def persist_normalized(lab_report: LabReport, normalized, *, replace: bool = True) -> list[LabResult]:
    if replace:
        lab_report.lab_results.clear()
    written: list[LabResult] = []
    for row in normalized:
        result = LabResult(
            lab_report_id=lab_report.id,
            biomarker_name=canonical_name_for_persist(row, None),
            raw_test_name=row.raw_test_name,
            value=row.value,
            unit=row.unit,
            reference_range_low=row.reference_range_low,
            reference_range_high=row.reference_range_high,
            status=row.status,
        )
        lab_report.lab_results.append(result)
        written.append(result)
    lab_report.status = LabReportStatus.COMPLETE
    lab_report.processing_stage = LabProcessingStage.COMPLETE
    lab_report.error_message = None
    lab_report.latest_report_id = None
    return written
