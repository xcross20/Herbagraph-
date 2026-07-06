"""Ensure demo lab report samples parse correctly."""

from pathlib import Path

import pytest

from app.pipeline.biomarker_normalizer import get_reference_data, normalize_lab_results
from app.pipeline.lab_parser import parse_lab_file

pytestmark = pytest.mark.unit

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "lab_reports"


@pytest.mark.parametrize(
    "filename,min_parsed,min_tracked",
    [
        ("demo_01_inflammatory_quest.txt", 5, 4),
        ("demo_02_metabolic_labcorp.txt", 5, 4),
        ("demo_03_comprehensive_quest.txt", 15, 12),
        ("demo_04_followup_improved.txt", 5, 4),
        ("demo_05_mixed_panel.csv", 5, 4),
        ("demo_06_pipe_delimited.txt", 3, 3),
    ],
)
def test_demo_lab_sample_parses(filename: str, min_parsed: int, min_tracked: int):
    path = SAMPLES_DIR / filename
    assert path.exists(), f"missing sample file: {path}"
    parsed = parse_lab_file(path.read_bytes(), path.name)
    normalized = normalize_lab_results(parsed)
    tracked = [n for n in normalized if get_reference_data(n.biomarker_name)]
    assert len(parsed) >= min_parsed, parsed
    assert len(tracked) >= min_tracked, [n.biomarker_name for n in normalized]