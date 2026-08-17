"""Load and validate lab scenario fixtures from samples/lab_scenarios/manifest.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.enums import RecommendationTree
from app.pipeline.biological_systems import compute_biological_systems
from app.pipeline.biomarker_normalizer import get_reference_data, normalize_lab_results
from app.pipeline.catalog_evidence import build_catalog_evidence_snippets, build_catalog_reasoning_output
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.lab_parser import parse_lab_file
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import route_recommendation_trees
from app.schemas.pipeline import NormalizedLabResult

SCENARIOS_ROOT = Path(__file__).resolve().parent.parent.parent / "samples" / "lab_scenarios"
MANIFEST_PATH = SCENARIOS_ROOT / "manifest.json"


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parsed_count: int = 0
    abnormal_count: int = 0
    primary_tree: str | None = None


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or MANIFEST_PATH
    with manifest_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def list_scenarios(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = manifest or load_manifest()
    return data["scenarios"]


def resolve_raw_path(scenario: dict[str, Any], scenarios_root: Path | None = None) -> Path:
    root = scenarios_root or SCENARIOS_ROOT
    raw_file = scenario["raw_file"]
    path = (root / raw_file).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Scenario {scenario['scenario_id']}: missing raw file {path}")
    return path


def _recommendation_names_for_normalized(
    normalized: list[NormalizedLabResult],
    *,
    custom_biomarkers: list[dict] | None = None,
) -> set[str]:
    """Run catalog-only recommendation pipeline; return intervention names surfaced."""
    abnormal = [n for n in normalized if n.status.value in ("critical_low", "low", "high", "critical_high")]
    if not abnormal:
        return set()

    pathways = map_pathways(normalized)
    routing = route_recommendation_trees(normalized, pathways)
    abnormal_names = {n.biomarker_name for n in abnormal}
    routed = build_interventions_for_routing(routing, pathways, normalized)
    interventions = {name for names in routed.values() for name in names}
    snippets = build_catalog_evidence_snippets(
        interventions,
        abnormal_biomarkers=abnormal_names,
        pathway_codes={p.pathway_code for p in pathways},
        routing=routing,
    )
    reasoning = build_catalog_reasoning_output(
        snippets,
        abnormal_biomarkers=abnormal_names,
        pathway_activations=pathways,
        routing=routing,
    )
    return {rec.intervention_name for rec in reasoning.recommendations}


def _recommendation_names_for_scenario(
    scenario: dict[str, Any],
    *,
    scenarios_root: Path | None = None,
) -> set[str]:
    path = resolve_raw_path(scenario, scenarios_root)
    custom_biomarkers = scenario.get("custom_biomarkers")
    parsed = parse_lab_file(path.read_bytes(), path.name)
    normalized = normalize_lab_results(parsed, custom_biomarkers=custom_biomarkers)
    return _recommendation_names_for_normalized(normalized, custom_biomarkers=custom_biomarkers)


def _match_normalized(
    normalized: list[NormalizedLabResult],
    spec: dict[str, Any],
) -> NormalizedLabResult | None:
    for lab in normalized:
        if lab.biomarker_name != spec.get("biomarker_name"):
            continue
        if "status" in spec and lab.status.value != spec["status"]:
            if not (spec["status"] == "normal" and lab.status.value == "optimal"):
                continue
        if "qualitative_label" in spec:
            label = (lab.qualitative_label or "").upper()
            expected = str(spec["qualitative_label"]).upper()
            if expected not in label and label != expected:
                continue
        return lab
    return None


def validate_scenario(
    scenario: dict[str, Any],
    *,
    scenarios_root: Path | None = None,
) -> ScenarioResult:
    """Run Tier 1–2 validation: parse, normalize, optional routing assertions."""
    scenario_id = scenario["scenario_id"]
    result = ScenarioResult(scenario_id=scenario_id, passed=True)

    if scenario.get("skip_ci"):
        result.warnings.append("skip_ci=true (not run in default CI parametrization)")
        return result

    try:
        path = resolve_raw_path(scenario, scenarios_root)
    except FileNotFoundError as exc:
        result.passed = False
        result.errors.append(str(exc))
        return result

    custom_biomarkers = scenario.get("custom_biomarkers")
    raw = path.read_bytes()
    parsed = parse_lab_file(raw, path.name)
    normalized = normalize_lab_results(parsed, custom_biomarkers=custom_biomarkers)
    result.parsed_count = len(parsed)
    abnormal = [n for n in normalized if n.status.value in ("critical_low", "low", "high", "critical_high")]
    result.abnormal_count = len(abnormal)

    expect = scenario.get("expect", {})

    parse_expect = expect.get("parse", {})
    min_rows = parse_expect.get("min_rows", 1)
    if len(parsed) < min_rows:
        result.passed = False
        result.errors.append(f"parse: expected >= {min_rows} rows, got {len(parsed)}")

    for spec in expect.get("normalize", {}).get("must_include", []):
        match = _match_normalized(normalized, spec)
        if match is None:
            result.passed = False
            result.errors.append(f"normalize: missing or mismatched {spec}")

    for name in expect.get("normalize", {}).get("must_track_in_catalog", []):
        if get_reference_data(name) is None:
            result.passed = False
            result.errors.append(f"normalize: {name!r} not in global catalog")

    for name in expect.get("normalize", {}).get("must_resolve_custom", []):
        match = next((n for n in normalized if n.biomarker_name == name), None)
        if match is None:
            result.passed = False
            result.errors.append(f"normalize: custom biomarker {name!r} not resolved")

    min_abnormal = expect.get("routing", {}).get("min_abnormal")
    if min_abnormal is not None and result.abnormal_count < min_abnormal:
        result.passed = False
        result.errors.append(f"routing: expected >= {min_abnormal} abnormal labs, got {result.abnormal_count}")

    max_abnormal = expect.get("routing", {}).get("max_abnormal")
    if max_abnormal is not None and result.abnormal_count > max_abnormal:
        result.passed = False
        result.errors.append(f"routing: expected <= {max_abnormal} abnormal labs, got {result.abnormal_count}")

    routing_expect = expect.get("routing", {})
    pathways = map_pathways(normalized)
    routing = route_recommendation_trees(normalized, pathways) if result.abnormal_count > 0 else None
    if routing is not None:
        result.primary_tree = routing.primary_tree.value if routing.primary_tree else None

    if routing_expect and result.abnormal_count > 0 and routing is not None:
        primary = result.primary_tree

        expected_primary = routing_expect.get("primary_tree")
        if expected_primary and primary != expected_primary:
            result.passed = False
            result.errors.append(f"routing: expected primary_tree={expected_primary!r}, got {primary!r}")

        for tree_name in routing_expect.get("trees", []):
            try:
                tree = RecommendationTree(tree_name)
            except ValueError:
                result.passed = False
                result.errors.append(f"routing: invalid tree name in manifest: {tree_name!r}")
                continue
            if tree not in routing.trees:
                result.passed = False
                result.errors.append(f"routing: expected tree {tree_name!r} not in {routing.trees}")

        for tree_name, biomarkers in routing_expect.get("biomarkers_by_tree", {}).items():
            try:
                tree = RecommendationTree(tree_name)
            except ValueError:
                result.passed = False
                result.errors.append(f"routing: invalid tree name: {tree_name!r}")
                continue
            routed = routing.biomarkers_by_tree.get(tree, [])
            for biomarker in biomarkers:
                if biomarker not in routed:
                    result.passed = False
                    result.errors.append(f"routing: expected {biomarker!r} under {tree_name!r}")

    elif routing_expect.get("primary_tree") == "signaling" and result.abnormal_count == 0:
        result.primary_tree = routing.primary_tree.value if routing and routing.primary_tree else None

    pathway_expect = expect.get("pathways", {})
    if pathway_expect and result.abnormal_count > 0:
        pathway_codes = {p.pathway_code for p in pathways}
        for code in pathway_expect.get("must_include", []):
            if code not in pathway_codes:
                result.passed = False
                result.errors.append(f"pathways: expected {code!r} not in activations")

    systems_expect = expect.get("biological_systems", {})
    if systems_expect and result.abnormal_count > 0:
        systems_by_code = {s["system_code"]: s for s in compute_biological_systems(pathways)}
        for spec in systems_expect.get("must_include", []):
            code = spec.get("system_code")
            if not code:
                continue
            system = systems_by_code.get(code)
            if system is None:
                result.passed = False
                result.errors.append(f"biological_systems: missing {code!r}")
                continue
            min_signal = spec.get("min_signal_level")
            if min_signal is not None and system["signal_level"] < min_signal:
                result.passed = False
                result.errors.append(
                    f"biological_systems: {code!r} signal_level {system['signal_level']} < {min_signal}"
                )

    rec_expect = expect.get("recommendations", {})
    if rec_expect and result.abnormal_count > 0 and routing is not None:
        abnormal_names = {n.biomarker_name for n in abnormal}
        routed = build_interventions_for_routing(routing, pathways, normalized)
        interventions = {name for names in routed.values() for name in names}
        snippets = build_catalog_evidence_snippets(
            interventions,
            abnormal_biomarkers=abnormal_names,
            pathway_codes={p.pathway_code for p in pathways},
            routing=routing,
        )
        reasoning = build_catalog_reasoning_output(
            snippets,
            abnormal_biomarkers=abnormal_names,
            pathway_activations=pathways,
            routing=routing,
        )
        rec_names = {rec.intervention_name for rec in reasoning.recommendations}
        for name in rec_expect.get("must_include", []):
            if name not in rec_names:
                result.passed = False
                result.errors.append(f"recommendations: expected {name!r} not routed")
        min_count = rec_expect.get("min_count")
        if min_count is not None and len(rec_names) < min_count:
            result.passed = False
            result.errors.append(f"recommendations: expected >= {min_count}, got {len(rec_names)}")

    trend_expect = expect.get("trend_pair")
    paired_id = scenario.get("paired_with")
    if trend_expect and paired_id:
        baseline = next(
            (s for s in list_scenarios() if s["scenario_id"] == paired_id),
            None,
        )
        if baseline is None:
            result.passed = False
            result.errors.append(f"trend_pair: unknown paired_with scenario {paired_id!r}")
        else:
            try:
                baseline_recs = _recommendation_names_for_scenario(baseline, scenarios_root=scenarios_root)
                followup_recs = _recommendation_names_for_scenario(scenario, scenarios_root=scenarios_root)
            except FileNotFoundError as exc:
                result.passed = False
                result.errors.append(f"trend_pair: {exc}")
            else:
                baseline_min = trend_expect.get("baseline_min_recommendations")
                if baseline_min is not None and len(baseline_recs) < baseline_min:
                    result.passed = False
                    result.errors.append(
                        f"trend_pair: baseline {paired_id!r} expected >= {baseline_min} "
                        f"recommendations, got {len(baseline_recs)}"
                    )
                max_recs = trend_expect.get("max_recommendations")
                if max_recs is not None and len(followup_recs) > max_recs:
                    result.passed = False
                    result.errors.append(
                        f"trend_pair: follow-up expected <= {max_recs} recommendations, "
                        f"got {len(followup_recs)}"
                    )
                min_drop = trend_expect.get("min_drop_from_baseline")
                if min_drop is not None and len(baseline_recs) - len(followup_recs) < min_drop:
                    result.passed = False
                    result.errors.append(
                        f"trend_pair: expected recommendation drop >= {min_drop}, "
                        f"baseline={len(baseline_recs)} followup={len(followup_recs)}"
                    )

    return result


def validate_all_scenarios(
    manifest: dict[str, Any] | None = None,
    *,
    scenarios_root: Path | None = None,
    skip_ci: bool = True,
) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for scenario in list_scenarios(manifest):
        if skip_ci and scenario.get("skip_ci"):
            continue
        results.append(validate_scenario(scenario, scenarios_root=scenarios_root))
    return results