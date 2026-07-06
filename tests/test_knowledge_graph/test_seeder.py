"""Tests for app.knowledge_graph.seeder against a real (temp-file) async SQLite session."""

import pytest
from sqlalchemy import func, select

from app.knowledge_graph.food_seed_data import (
    FOOD_COMPOUND_EVIDENCE_CLAIMS,
    FOOD_COMPOUND_SOURCES,
    FOOD_INTERVENTIONS,
    PHYTOCHEMICAL_COMPOUNDS,
)
from app.knowledge_graph.seed_data import BIOMARKERS, EVIDENCE_CLAIMS, INTERVENTIONS, PATHWAYS
from app.knowledge_graph.seeder import is_seeded, seed_knowledge_graph
from app.models.biomarker import Biomarker
from app.models.evidence import EvidenceClaim
from app.models.food_compound_source import FoodCompoundSource
from app.models.intervention import Intervention
from app.models.pathway import Pathway

pytestmark = pytest.mark.asyncio


async def _count(db_session, model):
    result = await db_session.execute(select(func.count()).select_from(model))
    return result.scalar()


async def test_is_seeded_false_before_seeding(db_session):
    assert await is_seeded(db_session) is False


async def test_is_seeded_true_after_seeding(db_session):
    await seed_knowledge_graph(db_session)
    assert await is_seeded(db_session) is True


async def test_seed_persists_correct_biomarker_count(db_session):
    await seed_knowledge_graph(db_session)
    assert await _count(db_session, Biomarker) == len(BIOMARKERS)


async def test_seed_persists_correct_pathway_count(db_session):
    await seed_knowledge_graph(db_session)
    assert await _count(db_session, Pathway) == len(PATHWAYS)


async def test_seed_persists_correct_intervention_count(db_session):
    await seed_knowledge_graph(db_session)
    expected = len(INTERVENTIONS) + len(PHYTOCHEMICAL_COMPOUNDS) + len(FOOD_INTERVENTIONS)
    assert await _count(db_session, Intervention) == expected


async def test_seed_persists_correct_evidence_claim_count(db_session):
    await seed_knowledge_graph(db_session)
    expected = len(EVIDENCE_CLAIMS) + len(FOOD_COMPOUND_EVIDENCE_CLAIMS)
    assert await _count(db_session, EvidenceClaim) == expected


async def test_seed_persists_correct_food_compound_source_count(db_session):
    await seed_knowledge_graph(db_session)
    assert await _count(db_session, FoodCompoundSource) == len(FOOD_COMPOUND_SOURCES)


async def test_seed_returns_matching_counts_dict(db_session):
    counts = await seed_knowledge_graph(db_session)
    assert counts["biomarkers"] == len(BIOMARKERS)
    assert counts["pathways"] == len(PATHWAYS)
    assert counts["interventions"] == len(INTERVENTIONS) + len(PHYTOCHEMICAL_COMPOUNDS) + len(
        FOOD_INTERVENTIONS
    )
    assert counts["evidence_claims"] == len(EVIDENCE_CLAIMS) + len(FOOD_COMPOUND_EVIDENCE_CLAIMS)
    assert counts["food_compound_sources"] == len(FOOD_COMPOUND_SOURCES)


async def test_beta_carotene_safety_flags_relationship(db_session):
    await seed_knowledge_graph(db_session)
    result = await db_session.execute(select(Intervention).where(Intervention.name == "Beta-Carotene"))
    beta_carotene = result.scalar_one()
    await db_session.refresh(beta_carotene, attribute_names=["safety_flags"])
    assert len(beta_carotene.safety_flags) == 1
    flag = beta_carotene.safety_flags[0]
    assert flag.condition == "smoking"
    assert flag.severity.value == "contraindication"


async def test_allicin_drug_interactions_relationship(db_session):
    await seed_knowledge_graph(db_session)
    result = await db_session.execute(select(Intervention).where(Intervention.name == "Allicin"))
    allicin = result.scalar_one()
    await db_session.refresh(allicin, attribute_names=["drug_interactions"])
    assert len(allicin.drug_interactions) == 1
    interaction = allicin.drug_interactions[0]
    assert interaction.drug_name == "Warfarin"


async def test_boswellia_safety_flag_and_drug_interaction_relationship(db_session):
    await seed_knowledge_graph(db_session)
    result = await db_session.execute(select(Intervention).where(Intervention.name == "Boswellia serrata"))
    boswellia = result.scalar_one()
    await db_session.refresh(boswellia, attribute_names=["safety_flags", "drug_interactions"])
    assert len(boswellia.safety_flags) == 1
    assert boswellia.safety_flags[0].condition == "pregnancy"
    assert len(boswellia.drug_interactions) == 1
    assert boswellia.drug_interactions[0].drug_name == "Warfarin"


async def test_seed_is_not_idempotent_double_seed_raises_or_duplicates(db_session):
    """seed_knowledge_graph is documented as not idempotent -- calling it twice should
    fail (unique constraint violation) rather than silently duplicate rows."""
    await seed_knowledge_graph(db_session)
    with pytest.raises(Exception):
        await seed_knowledge_graph(db_session)
