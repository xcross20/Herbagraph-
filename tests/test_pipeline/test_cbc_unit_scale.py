"""CBC absolute-count unit scaling and sex-aware Hgb classification."""

import pytest

from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import normalize_lab_result, normalize_lab_results
from app.pipeline.user_biomarker_profile import resolve_canonical_name
from app.schemas.pipeline import ParsedLabResult

pytestmark = pytest.mark.unit


def test_mychart_absolute_count_aliases():
    assert resolve_canonical_name("Neutrophils Absolute Count") == "Absolute Neutrophils"
    assert resolve_canonical_name("Monocytes Absolute Count") == "Absolute Monocytes"
    assert resolve_canonical_name("Eosinophils Absolute Count") == "Absolute Eosinophils"
    assert resolve_canonical_name("White Blood Cell Count") == "WBC"


def test_absolute_neutrophils_x10e3_not_falsely_low():
    """3.4 x10E3/uL with portal range 1.4–7.0 must not classify vs 1500–7800 cells."""
    parsed = ParsedLabResult(
        raw_test_name="Neutrophils Absolute Count",
        value=3.4,
        unit="x10E3/uL",
        reference_range_low=1.4,
        reference_range_high=7.0,
    )
    n = normalize_lab_result(parsed, sex="female")
    assert n.biomarker_name == "Absolute Neutrophils"
    assert n.status in (LabResultStatus.NORMAL, LabResultStatus.OPTIMAL)
    # Either kept portal scale with portal range, or scaled both to cells
    assert n.value in (3.4, 3400.0) or abs(n.value - 3400.0) < 0.1 or abs(n.value - 3.4) < 0.01


def test_absolute_lymphocytes_x10e3_not_falsely_low():
    parsed = ParsedLabResult(
        raw_test_name="Absolute Lymphocytes",
        value=2.6,
        unit="x10E3/uL",
        reference_range_low=0.7,
        reference_range_high=3.1,
    )
    n = normalize_lab_result(parsed)
    assert n.status in (LabResultStatus.NORMAL, LabResultStatus.OPTIMAL)


def test_absolute_monocytes_x10e3_not_falsely_low():
    parsed = ParsedLabResult(
        raw_test_name="Monocytes Absolute Count",
        value=0.6,
        unit="x10E3/uL",
        reference_range_low=0.1,
        reference_range_high=0.9,
    )
    n = normalize_lab_result(parsed)
    assert n.biomarker_name == "Absolute Monocytes"
    assert n.status in (LabResultStatus.NORMAL, LabResultStatus.OPTIMAL)


def test_female_hemoglobin_without_lab_range():
    parsed = ParsedLabResult(
        raw_test_name="Hemoglobin",
        value=12.1,
        unit="g/dL",
        reference_range_low=None,
        reference_range_high=None,
    )
    female = normalize_lab_result(parsed, sex="female")
    male = normalize_lab_result(parsed, sex="male")
    assert female.status in (LabResultStatus.NORMAL, LabResultStatus.OPTIMAL)
    assert male.status == LabResultStatus.LOW


def test_female_hemoglobin_with_lab_range_preferred():
    parsed = ParsedLabResult(
        raw_test_name="Hemoglobin",
        value=12.1,
        unit="g/dL",
        reference_range_low=11.1,
        reference_range_high=15.9,
    )
    n = normalize_lab_result(parsed, sex="male")  # lab range wins over male catalog
    assert n.status in (LabResultStatus.NORMAL, LabResultStatus.OPTIMAL)


def test_true_low_absolute_neutrophils_still_flags():
    """0.8 K/µL (800 cells) is truly low on both portal and catalog scales."""
    parsed = ParsedLabResult(
        raw_test_name="Absolute Neutrophils",
        value=0.8,
        unit="x10E3/uL",
        reference_range_low=1.4,
        reference_range_high=7.0,
    )
    n = normalize_lab_result(parsed)
    assert n.status == LabResultStatus.LOW


def test_cbc_batch_latest_values_mostly_normal_for_female():
    rows = [
        ParsedLabResult(
            raw_test_name=name,
            value=value,
            unit=unit,
            reference_range_low=lo,
            reference_range_high=hi,
        )
        for name, value, unit, lo, hi in [
            ("White Blood Cell Count", 6.8, "x10E3/uL", 3.4, 10.8),
            ("Neutrophils Absolute Count", 3.4, "x10E3/uL", 1.4, 7.0),
            ("Absolute Lymphocytes", 2.6, "x10E3/uL", 0.7, 3.1),
            ("Monocytes Absolute Count", 0.6, "x10E3/uL", 0.1, 0.9),
            ("Hemoglobin", 12.1, "g/dL", 11.1, 15.9),
            ("Hematocrit", 38.4, "%", 34.0, 46.6),
            ("Platelets", 393.0, "x10E3/uL", 150.0, 450.0),
        ]
    ]
    norm = normalize_lab_results(rows, sex="female")
    abn = [n for n in norm if n.status.value not in ("normal", "optimal")]
    assert abn == [], f"unexpected abnormals: {[(a.biomarker_name, a.value, a.status) for a in abn]}"
