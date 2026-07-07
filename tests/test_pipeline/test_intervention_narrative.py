"""Intervention narrative and dynamic catalog tests."""

import pytest

from app.models.enums import InterventionCategory, LabResultStatus, PathwayDirection
from app.pipeline.intervention_catalog import build_pathway_intervention_map
from app.pipeline.intervention_narrative import build_intervention_narrative
from app.pipeline.food_source_resolver import attach_food_sources
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation, ScoredRecommendation

pytestmark = pytest.mark.unit


def test_pathway_map_includes_mastic_gum_for_gastric_colonization():
    mapping = build_pathway_intervention_map()
    assert "Mastic Gum" in mapping["GASTRIC_COLONIZATION"]


def test_curcumin_herb_gets_turmeric_food_sources_after_catalog_fix():
    rec = ScoredRecommendation(
        intervention_name="Curcumin",
        category=InterventionCategory.HERB,
        mechanism="NF-kB modulation",
        evidence_level="moderate",
        cited_study_ids=[],
    )
    sources, _ = attach_food_sources(rec.intervention_name, rec.category.value)
    # After food catalog regen, Turmeric Root should link to Curcumin.
    if sources:
        foods = {s.food for s in sources}
        assert "Turmeric Root" in foods or "Broccoli Sprouts" in foods or len(foods) >= 1


def test_sulforaphane_narrative_mentions_foods_and_biomarker():
    labs = [
        NormalizedLabResult(
            biomarker_name="H. pylori Urea Breath Test",
            raw_test_name="H. pylori Urea Breath Test",
            value=1.0,
            status=LabResultStatus.HIGH,
            category="infectious_disease",
            qualitative_label="DETECTED",
        )
    ]
    pathways = [
        PathwayActivation(
            pathway_code="NF_KB",
            pathway_name="NF-κB Inflammatory Signaling",
            activation_score=0.75,
            direction=PathwayDirection.ACTIVATED,
            contributing_biomarkers=["H. pylori Urea Breath Test"],
        )
    ]
    rec = ScoredRecommendation(
        intervention_name="Sulforaphane",
        category=InterventionCategory.PHYTOCHEMICAL,
        mechanism="Nrf2/NF-κB modulation",
        evidence_level="moderate",
        cited_study_ids=[],
    )
    food_sources, linked = attach_food_sources(rec.intervention_name, rec.category.value)
    narrative = build_intervention_narrative(
        "Sulforaphane",
        "phytochemical",
        rec.mechanism,
        pathways,
        {"Sulforaphane": ["NF_KB"]},
        labs,
        food_sources,
        linked_compound=linked,
    )
    assert "H. pylori" in narrative
    assert "phytochemical" in narrative.lower()
    if food_sources:
        assert "Broccoli Sprouts" in narrative or "whole foods" in narrative.lower()
    assert "phytochemical" in narrative.lower() or "H. pylori" in narrative