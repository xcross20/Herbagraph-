"""Persisted LabResult rows should re-resolve to catalog names at report time."""

import pytest

from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import normalized_result_from_lab_result

pytestmark = pytest.mark.unit


class _FakeLabResult:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_persisted_mean_cell_mch_resolves_to_catalog_for_pathways():
    row = _FakeLabResult(
        biomarker_name="Mean Cell Hemoglobin (MCH)",
        raw_test_name="Mean Cell Hemoglobin (MCH)",
        value=36.5,
        unit="pg",
        reference_range_low=27.0,
        reference_range_high=32.0,
        status=LabResultStatus.HIGH,
    )
    normalized = normalized_result_from_lab_result(row)
    assert normalized.biomarker_name == "MCH"
    assert normalized.status == LabResultStatus.HIGH
    assert normalized.category == "cbc"