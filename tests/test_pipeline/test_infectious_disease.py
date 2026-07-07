"""Qualitative infectious disease / microbiology test handling."""

import pytest

from app.pipeline.biomarker_normalizer import get_reference_data, normalize_lab_result, normalize_lab_results
from app.pipeline.lab_parser import parse_lab_line
from app.pipeline.pathway_mapper import map_pathways
from app.schemas.pipeline import ParsedLabResult

pytestmark = pytest.mark.unit


def test_h_pylori_catalog_entry_is_qualitative():
    ref = get_reference_data("H. pylori Urea Breath Test")
    assert ref is not None
    assert ref["result_kind"] == "qualitative"
    assert ref["category"] == "infectious_disease"


def test_h_pylori_detected_normalizes_to_high():
    parsed = parse_lab_line(
        "HELICOBACTER PYLORI, UREA BREATH TEST DETECTED Reference Range: NOT DETECTED"
    )
    assert parsed is not None
    normalized = normalize_lab_result(parsed)
    assert normalized.biomarker_name == "H. pylori Urea Breath Test"
    assert normalized.status.value == "high"
    assert normalized.qualitative_label == "DETECTED"
    assert normalized.expected_label == "NOT DETECTED"


def test_h_pylori_not_detected_normalizes_to_optimal():
    parsed = ParsedLabResult(
        raw_test_name="HELICOBACTER PYLORI, UREA BREATH TEST",
        value=0.0,
        unit="NOT DETECTED",
        reference_range_low=0.0,
        reference_range_high=0.0,
        qualitative_result="NOT DETECTED",
        expected_result="NOT DETECTED",
    )
    normalized = normalize_lab_result(parsed)
    assert normalized.biomarker_name == "H. pylori Urea Breath Test"
    assert normalized.status.value == "optimal"


def test_urine_culture_organism_parses():
    parsed = parse_lab_line("URINE CULTURE    Escherichia coli")
    assert parsed is not None
    normalized = normalize_lab_result(parsed)
    assert normalized.biomarker_name == "Urine Culture"
    assert normalized.status.value == "high"
    assert "ESCHERICHIA" in normalized.qualitative_label


def test_urine_culture_no_growth_parses():
    parsed = parse_lab_line("URINE CULTURE    No growth")
    assert parsed is not None
    normalized = normalize_lab_result(parsed)
    assert normalized.biomarker_name == "Urine Culture"
    assert normalized.status.value == "optimal"


def test_cyp2d6_genotype_parses():
    parsed = parse_lab_line("CYP2D6    *1/*4    Intermediate Metabolizer")
    assert parsed is not None
    normalized = normalize_lab_result(parsed)
    assert normalized.biomarker_name == "CYP2D6 Genotype"
    assert normalized.qualitative_label is not None


def test_fecal_calprotectin_catalog_entry():
    ref = get_reference_data("Fecal Calprotectin")
    assert ref is not None
    assert ref["category"] == "gi_stool"


def test_h_pylori_positive_activates_inflammation_pathways():
    parsed = parse_lab_line(
        "HELICOBACTER PYLORI, UREA BREATH TEST DETECTED Reference Range: NOT DETECTED"
    )
    normalized = normalize_lab_results([parsed])
    pathways = map_pathways(normalized)
    codes = {p.pathway_code for p in pathways}
    assert "NF_KB" in codes
    assert any("H. pylori" in b for p in pathways for b in p.contributing_biomarkers)