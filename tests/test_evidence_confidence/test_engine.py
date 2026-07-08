"""Integration tests for the explainability engine."""

import pytest

from app.evidence_confidence.engine import explain_recommendation
from app.models.enums import EvidenceLevel, InterventionCategory, LabResultStatus, StudySource, StudyType
from app.schemas.pipeline import (
    EvidenceSnippet,
    LLMRecommendation,
    NormalizedLabResult,
    PathwayActivation,
)

pytestmark = pytest.mark.unit


def test_explain_recommendation_full_chain():
    rec = LLMRecommendation(
        intervention_name="Curcumin",
        category=InterventionCategory.PHYTOCHEMICAL,
        mechanism="Inhibits NF-κB signaling.",
        evidence_level=EvidenceLevel.MODERATE,
        cited_study_ids=["pm123"],
        typical_dose="500 mg twice daily",
    )
    evidence = [
        EvidenceSnippet(
            source=StudySource.PUBMED,
            external_id="pm123",
            title="Curcumin reduces CRP in adults",
            year=2021,
            study_type=StudyType.RCT,
            quality_score=0.75,
            intervention_name="Curcumin",
            abstract_snippet="Randomized trial n=120 showed reduced CRP.",
        )
    ]
    pathways = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-κB Inflammatory Signaling",
            activation_score=0.8,
            direction="activated",
            contributing_biomarkers=["CRP"],
        )
    ]
    labs = [
        NormalizedLabResult(
            biomarker_name="CRP",
            raw_test_name="CRP",
            value=5.2,
            unit="mg/L",
            status=LabResultStatus.HIGH,
            category="inflammation",
        )
    ]
    result = explain_recommendation(
        rec,
        evidence,
        pathways,
        {"Curcumin": ["NF_KB"]},
        labs,
        {"age_range": "40-49", "biological_sex": "female"},
    )

    assert result.intervention_name == "Curcumin"
    assert result.evidence_confidence_numeric > 0
    assert len(result.explanation_chain) >= 4
    assert any(link.link_type == "biomarker" for link in result.explanation_chain)
    assert any(link.link_type == "pathway" for link in result.explanation_chain)
    assert any(link.link_type == "evidence" for link in result.explanation_chain)
    assert result.supporting_biomarkers[0].biomarker_name == "CRP"
    assert result.supporting_pathways[0].pathway_code == "NF_KB"
    assert len(result.molecular_targets) >= 1
    assert result.evidence_timeline
    assert result.contradictory_evidence.positive_percent >= 0
    assert result.provenance
    assert result.versioning.explainability_engine_version
    assert result.evidence_passport is not None
    assert result.evidence_passport.quality_stars >= 1
    assert result.evidence_passport.confidence_label
    assert len(result.supporting_literature) >= 1
    assert result.supporting_literature[0].label
    assert result.supporting_literature[0].study_id == "pm123" or result.supporting_literature[0].study_id == "PMID:pm123"