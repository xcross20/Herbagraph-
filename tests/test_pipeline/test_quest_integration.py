"""Integration diagnostics across Stages 1-3 for real Quest PDF text."""

from pathlib import Path

import pytest

from app.pipeline.biomarker_normalizer import get_reference_data, normalize_lab_results
from app.pipeline.lab_parser import parse_lab_text
from app.pipeline.pathway_mapper import map_pathways

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "quest_labreport_excerpt.txt"


@pytest.fixture
def quest_text() -> str:
    if not FIXTURE.exists():
        pytest.skip("quest fixture not present")
    return FIXTURE.read_text()


def test_quest_fixture_stage1_parses_numeric_rows(quest_text):
    parsed = parse_lab_text(quest_text)
    assert len(parsed) >= 10


def test_quest_fixture_stage2_maps_mvp_biomarkers(quest_text):
    parsed = parse_lab_text(quest_text)
    normalized = normalize_lab_results(parsed)
    tracked = [n for n in normalized if get_reference_data(n.biomarker_name)]
    tracked_names = {n.biomarker_name for n in tracked}
    assert "Glucose" in tracked_names
    assert "Creatinine" in tracked_names
    assert "LDL" in tracked_names or "HDL" in tracked_names


def test_quest_fixture_stage3_pathway_mapping_runs(quest_text):
    parsed = parse_lab_text(quest_text)
    normalized = normalize_lab_results(parsed)
    tracked = [n for n in normalized if get_reference_data(n.biomarker_name)]
    pathways = map_pathways(tracked)
    assert isinstance(pathways, list)