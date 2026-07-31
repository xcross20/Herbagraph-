"""Provider-agnostic Stage 5 stabilization."""

import pytest

from app.models.enums import EvidenceLevel, InterventionCategory, PathwayDirection, StudySource, StudyType
from app.pipeline.catalog_evidence import stabilize_reasoning_output
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation, PathwayActivation

pytestmark = pytest.mark.unit


def _snippet(name: str, pmid: str, score: float = 0.9) -> EvidenceSnippet:
    return EvidenceSnippet(
        source=StudySource.PUBMED,
        external_id=pmid,
        title=f"{name} study",
        year=2024,
        study_type=StudyType.RCT,
        quality_score=score,
        intervention_name=name,
    )


def test_stabilize_uses_catalog_intervention_set_when_llm_omits_recs():
    evidence = [_snippet("Magnesium", "PMID:1"), _snippet("Omega-3", "PMID:2")]
    abnormal = {"CRP"}
    pathways = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-kB",
            activation_score=0.8,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["CRP"],
        )
    ]
    llm_output = LLMReasoningOutput(
        biomarker_pattern_analysis="LLM narrative",
        pathway_summaries=["LLM summary"],
        recommendations=[
            LLMRecommendation(
                intervention_name="Magnesium",
                category=InterventionCategory.SUPPLEMENT,
                mechanism="LLM mechanism",
                evidence_level=EvidenceLevel.MODERATE,
                cited_study_ids=["PMID:1"],
                rationale="LLM rationale",
            )
        ],
        clinician_questions=["LLM question?"],
    )

    stable = stabilize_reasoning_output(
        llm_output,
        evidence,
        abnormal_biomarkers=abnormal,
        pathway_activations=pathways,
    )

    names = [rec.intervention_name for rec in stable.recommendations]
    assert names == ["Magnesium", "Omega-3"]
    assert stable.recommendations[0].mechanism == "LLM mechanism"
    assert stable.recommendations[1].intervention_name == "Omega-3"
    assert stable.biomarker_pattern_analysis == "LLM narrative"


def test_stabilize_preserves_deterministic_order():
    evidence = [_snippet("Zinc", "PMID:9"), _snippet("Alpha-Lipoic Acid", "PMID:8")]
    abnormal = {"Glucose"}
    pathways = [
        PathwayActivation(
            pathway_code="AMPK",
            pathway_name="AMPK",
            activation_score=0.7,
            direction=PathwayDirection.SUPPRESSED,
            contributing_biomarkers=["Glucose"],
        )
    ]
    llm_output = LLMReasoningOutput(
        biomarker_pattern_analysis="",
        pathway_summaries=[],
        recommendations=[],
        clinician_questions=[],
    )

    stable = stabilize_reasoning_output(
        llm_output,
        evidence,
        abnormal_biomarkers=abnormal,
        pathway_activations=pathways,
    )

    assert [rec.intervention_name for rec in stable.recommendations] == [
        "Alpha-Lipoic Acid",
        "Zinc",
    ]