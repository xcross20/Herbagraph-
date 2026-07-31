"""Run lab scenarios through pipeline stages and collect structured outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.pipeline.adversarial_formats import MUTATION_IDS, apply_mutation
from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.catalog_evidence import build_catalog_evidence_snippets, build_catalog_reasoning_output
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.lab_parser import parse_lab_file
from app.pipeline.lab_scenario_loader import list_scenarios, resolve_raw_path
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import route_recommendation_trees
from app.pipeline.user_biomarker_profile import is_catalog_biomarker

_ABNORMAL = frozenset({"critical_low", "low", "high", "critical_high"})


@dataclass
class PipelineProbeResult:
    probe_id: str
    passed: bool
    parsed_count: int = 0
    abnormal_count: int = 0
    unresolved_abnormals: list[str] = field(default_factory=list)
    primary_tree: str | None = None
    recommendation_count: int = 0
    error: str | None = None


def _run_stages(
    raw: bytes,
    filename: str,
    *,
    custom_biomarkers: list[dict] | None = None,
    probe_id: str = "base",
) -> PipelineProbeResult:
    result = PipelineProbeResult(probe_id=probe_id, passed=True)
    try:
        parsed = parse_lab_file(raw, filename)
        result.parsed_count = len(parsed)
        normalized = normalize_lab_results(parsed, custom_biomarkers=custom_biomarkers)
        abnormal = [n for n in normalized if n.status.value in _ABNORMAL]
        result.abnormal_count = len(abnormal)

        if not custom_biomarkers:
            result.unresolved_abnormals = [
                n.biomarker_name
                for n in abnormal
                if not is_catalog_biomarker(n.biomarker_name)
            ]

        pathways = map_pathways(normalized)
        routing = route_recommendation_trees(normalized, pathways)
        result.primary_tree = routing.primary_tree.value if routing.primary_tree else None

        if result.abnormal_count > 0:
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
            result.recommendation_count = len(reasoning.recommendations)
    except Exception as exc:  # noqa: BLE001 - resilience probes must capture all failures
        result.passed = False
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def probe_scenario(
    scenario: dict,
    *,
    scenarios_root: Path | None = None,
    include_mutations: bool = True,
) -> list[PipelineProbeResult]:
    """Run base parse + optional adversarial mutations for one scenario."""
    path = resolve_raw_path(scenario, scenarios_root)
    custom = scenario.get("custom_biomarkers")
    raw_text = path.read_bytes().decode("utf-8", errors="replace")
    results = [
        _run_stages(
            path.read_bytes(),
            path.name,
            custom_biomarkers=custom,
            probe_id="base",
        )
    ]
    if include_mutations:
        for mutation_id in MUTATION_IDS:
            mutated = apply_mutation(raw_text, mutation_id)
            results.append(
                _run_stages(
                    mutated.encode("utf-8"),
                    path.name,
                    custom_biomarkers=custom,
                    probe_id=mutation_id,
                )
            )
    return results


def probe_all_scenarios(
    manifest: dict | None = None,
    *,
    scenarios_root: Path | None = None,
    skip_ci: bool = True,
    include_mutations: bool = True,
) -> list[PipelineProbeResult]:
    results: list[PipelineProbeResult] = []
    for scenario in list_scenarios(manifest):
        if skip_ci and scenario.get("skip_ci"):
            continue
        for probe in probe_scenario(scenario, scenarios_root=scenarios_root, include_mutations=include_mutations):
            probe.probe_id = f"{scenario['scenario_id']}:{probe.probe_id}"
            results.append(probe)
    return results