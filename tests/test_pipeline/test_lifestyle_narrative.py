"""Lifestyle intervention narratives include specific protocol methodology."""

import pytest

from app.pipeline.intervention_narrative import build_intervention_narrative

pytestmark = pytest.mark.unit


def test_box_breathing_narrative_includes_protocol():
    narrative = build_intervention_narrative(
        "Box Breathing (4-4-4-4)",
        "stress_reduction",
        "Paced breathing increases HRV.",
        [],
        {"Box Breathing (4-4-4-4)": ["HPA_AXIS"]},
        [],
        None,
    )
    assert "4 seconds" in narrative
    assert "studied protocol specifies" in narrative.lower()


def test_hiit_narrative_includes_methodology():
    narrative = build_intervention_narrative(
        "HIIT",
        "exercise",
        "Activates AMPK.",
        [],
        {"HIIT": ["AMPK"]},
        [],
        None,
    )
    assert "85–95% HRmax" in narrative or "85-95%" in narrative
    assert "structured exercise protocol" in narrative.lower()