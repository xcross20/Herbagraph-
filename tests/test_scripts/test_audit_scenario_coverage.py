"""CI gate thresholds for lab scenario matrix coverage."""

import importlib

import pytest

pytestmark = pytest.mark.unit


def test_scenario_coverage_minimums_match_ci_matrix_growth():
    mod = importlib.import_module("scripts.audit_scenario_coverage")

    assert mod.MIN_RECOMMENDATION_SCENARIOS >= 70
    assert mod.MIN_PATHWAY_SCENARIOS >= 70
    assert mod.MIN_BIOLOGICAL_SYSTEMS_SCENARIOS >= 70