"""Parametrized validation of samples/lab_scenarios/manifest.json."""

from __future__ import annotations

import json

import pytest

from app.pipeline.lab_scenario_loader import (
    MANIFEST_PATH,
    list_scenarios,
    validate_scenario,
)

pytestmark = pytest.mark.unit

SCENARIOS_ROOT = MANIFEST_PATH.parent


def _ci_scenarios() -> list[dict]:
    return [s for s in list_scenarios() if not s.get("skip_ci")]


@pytest.fixture(scope="module")
def manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_has_minimum_scenario_count(manifest: dict):
    scenarios = manifest["scenarios"]
    assert len(scenarios) >= 18
    ids = {s["scenario_id"] for s in scenarios}
    required = {
        "signaling_inflammatory_quest",
        "etiological_h_pylori_urea_breath",
        "exposure_h_pylori_igg",
        "culture_urine_positive",
        "celiac_ttg_iga_positive",
        "allergy_peanut_ige_high",
        "pgx_cyp2d6_intermediate",
        "autoimmune_ana_positive",
        "nutritional_vitd_low",
        "kitchen_sink_quest_excerpt",
    }
    assert required <= ids


@pytest.mark.parametrize("scenario", _ci_scenarios(), ids=lambda s: s["scenario_id"])
def test_lab_scenario_matrix(scenario: dict):
    result = validate_scenario(scenario, scenarios_root=SCENARIOS_ROOT)
    assert result.passed, f"{scenario['scenario_id']}: {result.errors}"


def test_each_routing_tree_represented():
    primaries: set[str] = set()
    all_trees: set[str] = set()
    for scenario in _ci_scenarios():
        routing = scenario.get("expect", {}).get("routing", {})
        if routing.get("primary_tree"):
            primaries.add(routing["primary_tree"])
        all_trees.update(routing.get("trees", []))
        if routing.get("primary_tree"):
            all_trees.add(routing["primary_tree"])

    assert {
        "signaling",
        "etiological",
        "exposure",
        "celiac",
        "allergy",
        "pgx_context",
        "autoimmune",
        "nutritional_repletion",
    } <= primaries
    assert "culture" in all_trees