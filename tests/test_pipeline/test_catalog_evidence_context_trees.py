"""CONTEXT_ONLY catalog evidence must surface for exposure and PGx routing trees."""

from pathlib import Path

import pytest

from app.models.enums import RecommendationTree
from app.pipeline.catalog_evidence import build_catalog_evidence_snippets
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import RecommendationRoutingContext, route_recommendation_trees
from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.lab_parser import parse_lab_file

pytestmark = pytest.mark.unit

_SCENARIO_DIR = Path(__file__).resolve().parents[2] / "samples" / "lab_scenarios" / "raw"


def _snippets_for_panel(panel: str, filename: str) -> list:
    parsed = parse_lab_file(panel.encode(), filename)
    normalized = normalize_lab_results(parsed)
    pathways = map_pathways(normalized)
    routing = route_recommendation_trees(normalized, pathways)
    routed = build_interventions_for_routing(routing, pathways, normalized)
    interventions = {name for names in routed.values() for name in names}
    abnormal = {
        lab.biomarker_name
        for lab in normalized
        if lab.status.value in ("critical_low", "low", "high", "critical_high")
    }
    return build_catalog_evidence_snippets(
        interventions,
        abnormal_biomarkers=abnormal,
        pathway_codes={p.pathway_code for p in pathways},
        routing=routing,
    )


def test_pgx_context_only_berberine_evidence_surfaces():
    panel = (_SCENARIO_DIR / "pgx_cyp2d6_intermediate.txt").read_text()
    snippets = _snippets_for_panel(panel, "pgx.txt")
    names = {s.intervention_name for s in snippets}
    assert "Berberine" in names


def test_exposure_context_only_mastic_evidence_surfaces():
    panel = (_SCENARIO_DIR / "exposure_h_pylori_igg.txt").read_text()
    snippets = _snippets_for_panel(panel, "exposure.txt")
    names = {s.intervention_name for s in snippets}
    assert "Mastic Gum" in names


def test_matching_claims_skips_context_only_on_signaling_only_tree():
    routing = RecommendationRoutingContext(
        trees=[RecommendationTree.SIGNALING],
        primary_tree=RecommendationTree.SIGNALING,
        biomarkers_by_tree={},
    )
    snippets = build_catalog_evidence_snippets(
        {"Berberine"},
        abnormal_biomarkers={"CYP2D6 Genotype"},
        pathway_codes={"DRUG_METABOLISM_VARIANT"},
        routing=routing,
    )
    assert not snippets