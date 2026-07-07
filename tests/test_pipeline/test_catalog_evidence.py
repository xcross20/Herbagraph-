"""Catalog-backed evidence injection for routed interventions."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models.enums import LabResultStatus
from app.pipeline.catalog_evidence import (
    build_catalog_evidence_snippets,
    build_catalog_reasoning_output,
    ensure_primary_recommendations,
)
from app.pipeline.evidence_retriever import retrieve_evidence
from app.pipeline.intervention_catalog import build_interventions_for_routing
from app.pipeline.llm_reasoner import parse_llm_response
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import route_recommendation_trees
from app.schemas.pipeline import NormalizedLabResult

pytestmark = pytest.mark.unit


def _h_pylori_lab() -> NormalizedLabResult:
    return NormalizedLabResult(
        biomarker_name="H. pylori Urea Breath Test",
        raw_test_name="H. pylori Urea Breath Test",
        value=1.0,
        status=LabResultStatus.HIGH,
        category="infectious_disease",
        qualitative_label="DETECTED",
    )


def test_catalog_snippets_include_mastic_gum_and_dgl_for_h_pylori():
    labs = [_h_pylori_lab()]
    pathways = map_pathways(labs)
    routing = route_recommendation_trees(labs, pathways)
    routed = build_interventions_for_routing(routing, pathways, labs)
    interventions = {name for names in routed.values() for name in names}

    snippets = build_catalog_evidence_snippets(
        interventions,
        abnormal_biomarkers={lab.biomarker_name for lab in labs},
        pathway_codes={p.pathway_code for p in pathways},
        routing=routing,
    )

    names = {snippet.intervention_name for snippet in snippets}
    assert "Mastic Gum" in names
    assert "DGL Licorice" in names
    mastic = next(s for s in snippets if s.intervention_name == "Mastic Gum")
    dgl = next(s for s in snippets if s.intervention_name == "DGL Licorice")
    assert mastic.external_id == "PMID:19879118"
    assert dgl.external_id == "PMID:493863"


@patch("app.pipeline.evidence_retriever.search_europepmc", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_clinicaltrials", new_callable=AsyncMock)
@patch("app.pipeline.evidence_retriever.search_pubmed", new_callable=AsyncMock)
async def test_retrieve_evidence_includes_catalog_when_live_sources_empty(
    mock_pubmed, mock_ct, mock_epmc
):
    mock_pubmed.return_value = []
    mock_ct.return_value = []
    mock_epmc.return_value = []

    labs = [_h_pylori_lab()]
    pathways = map_pathways(labs)
    routing = route_recommendation_trees(labs, pathways)

    result = await retrieve_evidence(pathways, routing=routing, normalized_labs=labs)
    names = {snippet.intervention_name for snippet in result}

    assert "Mastic Gum" in names
    assert "DGL Licorice" in names
    assert all(snippet.external_id.startswith("PMID:") for snippet in result)


def test_build_catalog_reasoning_output_surfaces_b12_folate_iron_for_macrocytic_cbc():
    panel = """\
Mean Cell Hemoglobin (MCH)    36.5  pg    (27.00-32.00)
Mean Cell Volume (MCV)    109.6  fL    (80.00-100.00)
Red Cell Distribution Width (RDW)    16.0  %    (11.50-14.50)
"""
    from app.pipeline.biomarker_normalizer import normalize_lab_results
    from app.pipeline.lab_parser import parse_lab_file

    parsed = parse_lab_file(panel.encode(), "cbc.txt")
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

    output = build_catalog_reasoning_output(
        snippets,
        abnormal_biomarkers=abnormal,
        pathway_activations=pathways,
        routing=routing,
    )
    names = {rec.intervention_name for rec in output.recommendations}
    assert {"B12", "Folate", "Iron"}.issubset(names)


def test_ensure_primary_recommendations_injects_mastic_and_dgl_when_llm_skips_them():
    labs = [_h_pylori_lab()]
    pathways = map_pathways(labs)
    routing = route_recommendation_trees(labs, pathways)
    routed = build_interventions_for_routing(routing, pathways, labs)
    interventions = {name for names in routed.values() for name in names}
    snippets = build_catalog_evidence_snippets(
        interventions,
        abnormal_biomarkers={lab.biomarker_name for lab in labs},
        pathway_codes={p.pathway_code for p in pathways},
        routing=routing,
    )

    llm_output = parse_llm_response(
        json.dumps(
            {
                "biomarker_pattern_analysis": "Active H. pylori detected.",
                "pathway_summaries": [],
                "recommendations": [
                    {
                        "intervention_name": "Curcumin",
                        "category": "phytochemical",
                        "mechanism": "NF-kB modulation",
                        "evidence_level": "low",
                        "typical_dose": None,
                        "cited_study_ids": ["PMID:19811613"],
                        "rationale": "Inflammation pathway",
                        "limitations": "Not eradication monotherapy",
                    }
                ],
                "clinician_questions": [],
            }
        ),
        snippets,
    )

    boosted = ensure_primary_recommendations(
        llm_output,
        snippets,
        abnormal_biomarkers={lab.biomarker_name for lab in labs},
        routing=routing,
    )
    names = [rec.intervention_name for rec in boosted.recommendations]
    assert names[0] == "Mastic Gum"
    assert "DGL Licorice" in names