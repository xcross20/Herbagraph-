"""Regenerate should remap stale garbled biomarker_name rows to catalog names."""

import pytest

from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import refresh_persisted_lab_results
from app.pipeline.user_biomarker_profile import is_catalog_biomarker

pytestmark = pytest.mark.unit


class _FakeRow:
    def __init__(self, biomarker_name: str, raw_test_name: str | None = None):
        self.biomarker_name = biomarker_name
        self.raw_test_name = raw_test_name
        self.value = 142.0
        self.unit = "mg/dL"
        self.reference_range_low = 0.0
        self.reference_range_high = 99.0
        self.status = LabResultStatus.HIGH


def test_refresh_persisted_lab_results_remaps_f_ldl_to_catalog():
    row = _FakeRow("F LDL Cholesterol Calc", raw_test_name=None)
    updated = refresh_persisted_lab_results([row])
    assert updated == 1
    assert row.biomarker_name == "LDL"
    assert is_catalog_biomarker(row.biomarker_name)


def test_refresh_persisted_lab_results_remaps_fhdl_concatenated():
    row = _FakeRow("FHDL", raw_test_name="FHDL")
    updated = refresh_persisted_lab_results([row])
    assert updated == 1
    assert row.biomarker_name == "HDL"