"""End-to-end macrocytic CBC panel: alias → pathway → routing → evidence."""

import pytest

from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.catalog_evidence import build_catalog_evidence_snippets
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.lab_parser import parse_lab_file
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import route_recommendation_trees

pytestmark = pytest.mark.unit

_CBC_PANEL = """\
Mean Cell Hemoglobin (MCH)    36.5  pg    (27.00-32.00)
Mean Cell Volume (MCV)    109.6  fL    (80.00-100.00)
Red Cell Distribution Width (RDW)    16.0  %    (11.50-14.50)
"""


def test_macrocytic_cbc_panel_produces_nutrient_signals_and_recommendations():
    parsed = parse_lab_file(_CBC_PANEL.encode(), "cbc.txt")
    normalized = normalize_lab_results(parsed)
    abnormal = {lab.biomarker_name for lab in normalized if lab.status.value in ("high", "critical_high")}

    assert abnormal == {"MCH", "MCV", "RDW"}

    pathways = map_pathways(normalized)
    pathway_codes = {p.pathway_code for p in pathways}
    assert "ONE_CARBON_METHYLATION" in pathway_codes
    assert "NUTRIENT_DEFICIENCY" in pathway_codes
    assert "IRON_HEPCIDIN" in pathway_codes

    routing = route_recommendation_trees(normalized, pathways)
    assert routing.primary_tree.value == "nutritional_repletion"

    routed = build_interventions_for_routing(routing, pathways, normalized)
    interventions = {name for names in routed.values() for name in names}
    assert "B12" in interventions
    assert "Folate" in interventions
    assert "Iron" in interventions

    snippets = build_catalog_evidence_snippets(
        interventions,
        abnormal_biomarkers=abnormal,
        pathway_codes=pathway_codes,
        routing=routing,
    )
    snippet_names = {s.intervention_name for s in snippets}
    assert "B12" in snippet_names
    assert "Folate" in snippet_names
    assert "Iron" in snippet_names