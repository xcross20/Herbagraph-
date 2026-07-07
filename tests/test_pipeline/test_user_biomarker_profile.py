"""User biomarker profile and supplemental alias tests."""

import pytest

from app.pipeline.biomarker_normalizer import normalize_lab_result
from app.pipeline.lab_parser import parse_lab_line
from app.pipeline.report_generator import _biomarker_summary
from app.pipeline.user_biomarker_profile import (
    prune_custom_biomarkers_overlapping_catalog,
    register_discovered_biomarkers,
    resolve_canonical_name,
)

pytestmark = pytest.mark.unit


def test_ldl_cholesterol_calc_aliases_to_ldl():
    assert resolve_canonical_name("LDL Cholesterol Calc") == "LDL"


@pytest.mark.parametrize(
    "raw_name,canonical",
    [
        ("Mean Cell Hemoglobin (MCH)", "MCH"),
        ("Mean Cell Volume (MCV)", "MCV"),
        ("Red Cell Distribution Width (RDW)", "RDW"),
        ("Mean Cell Hemoglobin Concentration (MCHC)", "MCHC"),
    ],
)
def test_mean_cell_cbc_aliases_resolve_to_catalog(raw_name, canonical):
    assert resolve_canonical_name(raw_name) == canonical


def test_supplemental_aliases_override_stale_custom_profile_entries():
    stale_profile = [
        {
            "canonical_name": "Mean Cell Hemoglobin (MCH)",
            "aliases": ["mean cell hemoglobin mch"],
            "unit": "pg",
            "reference_low": 27,
            "reference_high": 32,
        }
    ]
    assert resolve_canonical_name("Mean Cell Hemoglobin (MCH)", stale_profile) == "MCH"


def test_prune_custom_biomarkers_removes_catalog_duplicates():
    profile = [
        {
            "canonical_name": "Mean Cell Volume (MCV)",
            "aliases": ["mean cell volume mcv"],
            "unit": "fL",
            "reference_low": 80,
            "reference_high": 100,
        },
        {
            "canonical_name": "Lp(a) Mass",
            "aliases": ["lipoprotein a mass"],
            "unit": "mg/dL",
            "reference_low": 0,
            "reference_high": 30,
        },
    ]
    pruned = prune_custom_biomarkers_overlapping_catalog(profile)
    assert len(pruned) == 1
    assert pruned[0]["canonical_name"] == "Lp(a) Mass"


def test_parser_handles_compact_hdl_line():
    parsed = parse_lab_line("HDL 52.0 L 60.00 - 180.00 (mg/dL)")
    assert parsed is not None
    assert parsed.raw_test_name == "HDL"
    assert parsed.value == 52.0
    assert parsed.unit == "mg/dL"


def test_parser_handles_ldl_near_optimal_line():
    parsed = parse_lab_line("LDL Cholesterol Calc 109.4 NEAR OPTIMAL 0.00 - 100.00")
    assert parsed is not None
    assert parsed.raw_test_name == "LDL Cholesterol Calc"
    assert parsed.value == 109.4


def test_register_discovered_biomarkers_adds_unknown_tests():
    from app.schemas.pipeline import NormalizedLabResult
    from app.models.enums import LabResultStatus

    labs = [
        NormalizedLabResult(
            biomarker_name="Lp(a) Mass",
            raw_test_name="Lipoprotein(a) Mass",
            value=95.0,
            unit="mg/dL",
            reference_range_low=0.0,
            reference_range_high=30.0,
            status=LabResultStatus.HIGH,
            category="other",
        )
    ]
    updated = register_discovered_biomarkers(labs, [])
    assert len(updated) == 1
    assert updated[0]["canonical_name"] == "Lp(a) Mass"


def test_report_summary_includes_catalog_and_profile_biomarkers():
    from app.models.enums import LabResultStatus
    from app.schemas.pipeline import NormalizedLabResult

    labs = [
        NormalizedLabResult(
            biomarker_name="CRP",
            raw_test_name="CRP",
            value=8.0,
            unit="mg/L",
            reference_range_low=0.0,
            reference_range_high=3.0,
            status=LabResultStatus.HIGH,
            category="inflammatory",
        ),
        NormalizedLabResult(
            biomarker_name="Lp(a) Mass",
            raw_test_name="Lipoprotein(a) Mass",
            value=95.0,
            unit="mg/dL",
            reference_range_low=0.0,
            reference_range_high=30.0,
            status=LabResultStatus.HIGH,
            category="other",
        ),
    ]
    custom = [{"canonical_name": "Lp(a) Mass", "aliases": ["lipoprotein a mass"]}]
    summary = _biomarker_summary(labs, custom)
    names = {row["biomarker_name"] for row in summary["measured_biomarkers"]}
    assert names == {"CRP", "Lp(a) Mass"}


def test_hdl_ldl_end_to_end_from_user_formats():
    for line in [
        "HDL 52.0 L 60.00 - 180.00 (mg/dL)",
        "LDL Cholesterol Calc 109.4 NEAR OPTIMAL 0.00 - 100.00",
    ]:
        parsed = parse_lab_line(line)
        normalized = normalize_lab_result(parsed)
        assert normalized.biomarker_name in {"HDL", "LDL"}
        assert normalized.status.value in {"low", "high", "normal", "optimal"}