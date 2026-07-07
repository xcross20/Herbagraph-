"""Trend-pair scenario validation: baseline abnormal → recommendations; follow-up normal → none."""

import pytest

from app.pipeline.lab_scenario_loader import load_manifest, validate_scenario

pytestmark = pytest.mark.unit

SCENARIOS_ROOT = (
    __import__("pathlib").Path(__file__).resolve().parents[2] / "samples" / "lab_scenarios"
)


def test_trend_followup_drops_recommendations_vs_baseline():
    manifest = load_manifest()
    followup = next(s for s in manifest["scenarios"] if s["scenario_id"] == "trend_followup_improved")
    result = validate_scenario(followup, scenarios_root=SCENARIOS_ROOT)
    assert result.passed, result.errors