"""Medication context and lab trend context modules."""

import pytest

from app.pipeline.medication_context import build_medication_context
from app.pipeline.trend_context import build_trend_context
from app.schemas.pipeline import NormalizedLabResult
from app.models.enums import LabResultStatus

pytestmark = pytest.mark.unit


def _lab(name: str, value: float, status: LabResultStatus = LabResultStatus.HIGH) -> NormalizedLabResult:
    return NormalizedLabResult(
        biomarker_name=name,
        raw_test_name=name,
        value=value,
        unit="mg/dL",
        reference_range_low=0,
        reference_range_high=100,
        status=status,
    )


def test_medication_context_metformin_flags_b12():
    ctx = build_medication_context(
        [_lab("B12", 180, LabResultStatus.LOW)],
        {"current_medications": ["metformin 500mg"], "current_supplements": []},
    )
    assert ctx["has_medications"] is True
    assert any("B12" in n["biomarker_name"] for n in ctx["biomarker_specific_notes"])


def test_medication_context_empty_profile():
    ctx = build_medication_context([_lab("CRP", 5)], {})
    assert ctx["has_medications"] is False
    assert ctx["notes"] == []


def test_trend_context_no_prior():
    ctx = build_trend_context([_lab("CRP", 5)], None)
    assert ctx["has_prior_labs"] is False


def test_trend_context_improved_crp():
    prior = [_lab("CRP", 8, LabResultStatus.HIGH)]
    current = [_lab("CRP", 2, LabResultStatus.OPTIMAL)]
    ctx = build_trend_context(current, prior, prior_report_date="2025-01-01")
    assert ctx["has_prior_labs"] is True
    assert ctx["compared_biomarkers"] == 1
    assert ctx["trends"][0]["direction"] == "improved"
    assert ctx["improved_count"] == 1