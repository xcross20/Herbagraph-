"""Unit tests for report methodology builder."""

import pytest

from app.pipeline.report_methodology import build_report_methodology

pytestmark = pytest.mark.unit


def test_methodology_includes_seven_steps_for_iron_panel():
    methodology = build_report_methodology(
        {
            "total_biomarkers": 1,
            "measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}],
        },
        [{"system_name": "Nutrient Status", "signal_level": 2}],
        [{"pathway_name": "Iron/Hepcidin Regulation", "pathway_code": "IRON_HEPCIDIN", "activation_score": 0.8}],
        [{"intervention_name": "Iron"}],
        citations=[{"study_type": "rct"}],
    )
    assert methodology["heading"] == "How This Report Was Generated"
    assert len(methodology["steps"]) == 7
    assert "Iron" in methodology["steps"][1]["description"]
    assert "Nutrient Status" in methodology["steps"][2]["description"]
    assert "rct" in methodology["steps"][4]["description"].lower()