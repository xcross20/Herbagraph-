"""Healow/eClinicalWorks PDF lipid panel formats (F-column + <= ranges)."""

from pathlib import Path

import pytest

from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.lab_parser import parse_lab_text
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.user_biomarker_profile import is_catalog_biomarker, resolve_canonical_name

pytestmark = pytest.mark.unit

_EXCERPT = Path(__file__).resolve().parents[1] / "fixtures" / "healow_lipid_panel_excerpt.txt"


def test_resolve_canonical_name_does_not_crash_on_prefix_ocr_variants():
    """Regression: prefix_variants must flatten OCR variant lists, not nest them."""
    assert resolve_canonical_name("F HDL") == "HDL"


@pytest.mark.parametrize(
    "line,canonical",
    [
        ("F Cholesterol, Total 174.0 100.00 - 200.00 (mg/dL)", "Total Cholesterol"),
        ("F Triglycerides 63.0 <= 150.00 (mg/dL)", "Triglycerides"),
        ("F HDL 52.0 L 60.00 - 180.00 (mg/dL)", "HDL"),
        ("F LDL Cholesterol Calc 109.4 NEAR OPTIMAL 0.00 - 100.00", "LDL"),
        ("F Non-HDL Cholesterol 122.0 1.00 - 130.00", "Non-HDL Cholesterol"),
        ("F Total Cholesterol/HDL Ratio 3.35 1.00 - 5.00", "Chol/HDL Ratio"),
    ],
)
def test_healow_lipid_lines_parse_and_resolve(line, canonical):
    parsed = parse_lab_text(line)
    assert len(parsed) == 1
    normalized = normalize_lab_results(parsed)[0]
    assert normalized.biomarker_name == canonical
    assert is_catalog_biomarker(normalized.biomarker_name)


def test_healow_excerpt_all_rows_in_catalog():
    parsed = parse_lab_text(_EXCERPT.read_text())
    assert len(parsed) == 6
    normalized = normalize_lab_results(parsed)
    assert all(is_catalog_biomarker(n.biomarker_name) for n in normalized)


def test_healow_excerpt_ldl_high_fires_hepatic_lipid():
    parsed = parse_lab_text(_EXCERPT.read_text())
    normalized = normalize_lab_results(parsed)
    codes = {p.pathway_code for p in map_pathways(normalized)}
    assert "HEPATIC_LIPID" in codes