"""Adversarial format mutations + full catalog pipeline must not crash."""

from __future__ import annotations

import pytest

from app.pipeline.adversarial_formats import MUTATION_IDS, apply_mutation
from app.pipeline.lab_scenario_loader import list_scenarios, resolve_raw_path
from app.pipeline.pipeline_resilience import probe_all_scenarios, probe_scenario

pytestmark = pytest.mark.unit

SCENARIOS_ROOT = resolve_raw_path(list_scenarios()[0]).parent.parent


def _ci_scenarios() -> list[dict]:
    return [s for s in list_scenarios() if not s.get("skip_ci")]


def test_all_scenarios_and_mutations_survive_pipeline():
    results = probe_all_scenarios(skip_ci=True, include_mutations=True)
    crashes = [r for r in results if not r.passed]
    assert not crashes, [(r.probe_id, r.error) for r in crashes]


def test_minimum_probe_count_covers_matrix():
    results = probe_all_scenarios(skip_ci=True, include_mutations=True)
    scenarios = _ci_scenarios()
    expected = len(scenarios) * (1 + len(MUTATION_IDS))
    assert len(results) == expected


@pytest.mark.parametrize("mutation_id", MUTATION_IDS)
def test_mutation_operators_are_defined(mutation_id: str):
    path = resolve_raw_path(_ci_scenarios()[0], SCENARIOS_ROOT)
    text = path.read_text(encoding="utf-8")
    mutated = apply_mutation(text, mutation_id)
    assert mutated != "" or text == ""


@pytest.mark.parametrize("scenario", _ci_scenarios(), ids=lambda s: s["scenario_id"])
def test_scenario_base_probe_matches_validate_scenario(scenario: dict):
    """Resilience probe should agree with manifest validate_scenario for base path."""
    from app.pipeline.lab_scenario_loader import validate_scenario

    validation = validate_scenario(scenario, scenarios_root=SCENARIOS_ROOT)
    probes = probe_scenario(scenario, scenarios_root=SCENARIOS_ROOT, include_mutations=False)
    base = probes[0]

    assert base.passed, base.error
    assert base.parsed_count == validation.parsed_count
    assert base.abnormal_count == validation.abnormal_count
    if validation.primary_tree:
        assert base.primary_tree == validation.primary_tree