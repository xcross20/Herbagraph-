"""Lab scenario matrix contract tests."""

import pytest

from app.pipeline.lab_scenario_loader import list_scenarios, load_manifest, validate_all_scenarios

pytestmark = pytest.mark.unit

MIN_SCENARIOS_WITH_RECOMMENDATION_ASSERTS = 12


def test_ci_scenarios_all_pass():
    results = validate_all_scenarios(skip_ci=True)
    failures = [r for r in results if not r.passed]
    assert not failures, [f"{r.scenario_id}: {r.errors}" for r in failures]


def test_at_least_twelve_scenarios_assert_recommendations():
    manifest = load_manifest()
    scenarios = [s for s in list_scenarios(manifest) if not s.get("skip_ci")]
    with_recs = [s for s in scenarios if s.get("expect", {}).get("recommendations")]
    assert len(with_recs) >= MIN_SCENARIOS_WITH_RECOMMENDATION_ASSERTS, (
        f"expected >= {MIN_SCENARIOS_WITH_RECOMMENDATION_ASSERTS}, got {len(with_recs)}: "
        f"{[s['scenario_id'] for s in with_recs]}"
    )


def test_routing_trees_with_recommendations_include_required_trees():
    manifest = load_manifest()
    required_trees = {
        "etiological",
        "celiac",
        "nutritional_repletion",
        "allergy",
        "exposure",
        "pgx_context",
    }
    covered: set[str] = set()
    for scenario in list_scenarios(manifest):
        if scenario.get("skip_ci"):
            continue
        rec_expect = scenario.get("expect", {}).get("recommendations")
        if not rec_expect:
            continue
        primary = scenario.get("expect", {}).get("routing", {}).get("primary_tree")
        if primary:
            covered.add(primary)
    missing = required_trees - covered
    assert not missing, f"no recommendation asserts for routing trees: {sorted(missing)}"