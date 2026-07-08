"""Tests for multi-lab biomarker merge rules."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.enums import LabResultStatus
from app.models.lab import LabResult
from app.pipeline.integrated_merge import infer_panel_label, merge_lab_reports

pytestmark = pytest.mark.unit


def _lab_result(name: str, value: float, unit: str = "mg/dL", status: LabResultStatus = LabResultStatus.NORMAL):
    return LabResult(
        lab_report_id=uuid.uuid4(),
        biomarker_name=name,
        raw_test_name=name,
        value=value,
        unit=unit,
        status=status,
    )


def _report(filename: str, results: list[LabResult], created_at: datetime):
    report_id = uuid.uuid4()
    for row in results:
        row.lab_report_id = report_id
    return SimpleNamespace(
        id=report_id,
        original_filename=filename,
        created_at=created_at,
        lab_results=results,
    )


def test_infer_panel_label_from_filename():
    assert infer_panel_label("patient_cbc_2024.pdf") == "CBC"
    assert infer_panel_label("lipid-panel.txt") == "Lipid Panel"


def test_merge_combines_distinct_biomarkers_from_multiple_reports():
    older = _report(
        "cbc.txt",
        [_lab_result("CRP", 8.2, "mg/L", LabResultStatus.HIGH)],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    newer = _report(
        "cmp.txt",
        [_lab_result("Glucose", 95.0)],
        datetime(2024, 6, 1, tzinfo=timezone.utc),
    )

    merged = merge_lab_reports([older, newer])

    assert len(merged.snapshot) == 2
    names = {row.biomarker_name for row in merged.snapshot}
    assert names == {"CRP", "Glucose"}
    assert len(merged.sources) == 2


def test_merge_prefers_most_recent_value_for_same_biomarker():
    older = _report(
        "crp_old.txt",
        [_lab_result("CRP", 5.0, "mg/L", LabResultStatus.HIGH)],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    newer = _report(
        "crp_new.txt",
        [_lab_result("CRP", 2.5, "mg/L", LabResultStatus.LOW)],
        datetime(2024, 6, 1, tzinfo=timezone.utc),
    )

    merged = merge_lab_reports([older, newer])
    crp = next(row for row in merged.snapshot if row.biomarker_name == "CRP")

    assert crp.value == 2.5
    historical = [row for row in merged.integrated_rows if row["biomarker_name"] == "CRP" and not row["is_snapshot"]]
    assert len(historical) == 1
    assert historical[0]["value"] == 5.0


def test_merge_flags_same_day_conflicts():
    day = datetime(2024, 3, 15, tzinfo=timezone.utc)
    report_a = _report("a.txt", [_lab_result("CRP", 4.0, "mg/L", LabResultStatus.HIGH)], day)
    report_b = _report("b.txt", [_lab_result("CRP", 9.0, "mg/L", LabResultStatus.HIGH)], day)

    merged = merge_lab_reports([report_a, report_b])

    assert merged.conflicts
    assert merged.conflicts[0]["biomarker_name"] == "CRP"
    assert len(merged.conflicts[0]["values"]) >= 2