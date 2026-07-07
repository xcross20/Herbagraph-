"""Catalog-only reasoning path (no OpenAI) for CI and local tests."""

import pytest

from app.pipeline.catalog_evidence import build_catalog_evidence_snippets
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.llm_reasoner import generate_reasoning
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import route_recommendation_trees
from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.lab_parser import parse_lab_file

pytestmark = pytest.mark.unit

_PANEL = """\
Mean Cell Hemoglobin (MCH)    36.5  pg    (27.00-32.00)
Mean Cell Volume (MCV)    109.6  fL    (80.00-100.00)
Red Cell Distribution Width (RDW)    16.0  %    (11.50-14.50)
"""


@pytest.mark.asyncio
async def test_generate_reasoning_uses_catalog_path_with_test_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-api-key")
    from app.config import get_settings

    get_settings.cache_clear()

    parsed = parse_lab_file(_PANEL.encode(), "cbc.txt")
    normalized = normalize_lab_results(parsed)
    pathways = map_pathways(normalized)
    routing = route_recommendation_trees(normalized, pathways)
    routed = build_interventions_for_routing(routing, pathways, normalized)
    interventions = {name for names in routed.values() for name in names}
    abnormal = {lab.biomarker_name for lab in normalized if lab.status.value in ("high", "critical_high")}
    snippets = build_catalog_evidence_snippets(
        interventions,
        abnormal_biomarkers=abnormal,
        pathway_codes={p.pathway_code for p in pathways},
        routing=routing,
    )

    output = await generate_reasoning(normalized, pathways, snippets, {}, routing=routing)
    names = {rec.intervention_name for rec in output.recommendations}
    assert {"B12", "Folate", "Iron"}.issubset(names)

    get_settings.cache_clear()