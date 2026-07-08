"""Healow/eClinicalWorks HbA1c panel (F-prefix + < upper-bound reference)."""

from pathlib import Path

import pytest

from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.lab_parser import parse_lab_file, parse_lab_text
from app.pipeline.pathway_mapper import map_pathways

pytestmark = pytest.mark.unit

_EXCERPT = Path(__file__).resolve().parents[1] / "fixtures" / "healow_hba1c_excerpt.txt"
_HEALOW_PDF = Path("/Users/immanuellewis/Downloads/Healow (2).pdf")


def test_healow_hba1c_lt_range_line_parses_and_normalizes():
    parsed = parse_lab_text("F HbA1c 5.9 H < 5.70 (%)")
    assert len(parsed) == 1
    assert parsed[0].raw_test_name == "HbA1c"
    assert parsed[0].value == 5.9
    assert parsed[0].reference_range_high == 5.70

    normalized = normalize_lab_results(parsed)[0]
    assert normalized.biomarker_name == "HbA1c"
    assert normalized.status == LabResultStatus.HIGH


def test_healow_hba1c_excerpt_fires_metabolic_pathway():
    parsed = parse_lab_text(_EXCERPT.read_text(encoding="utf-8"))
    names = {row.raw_test_name for row in parsed}
    assert "HbA1c" in names

    normalized = normalize_lab_results(parsed)
    hba1c = next(n for n in normalized if n.biomarker_name == "HbA1c")
    codes = {p.pathway_code for p in map_pathways([hba1c])}
    assert "INSULIN_PI3K_AKT" in codes


@pytest.mark.skipif(not _HEALOW_PDF.is_file(), reason="Local Healow (2).pdf not available")
def test_healow_hba1c_pdf_parses_without_llm():
    parsed = parse_lab_file(_HEALOW_PDF.read_bytes(), _HEALOW_PDF.name)
    assert any(p.raw_test_name == "HbA1c" for p in parsed)