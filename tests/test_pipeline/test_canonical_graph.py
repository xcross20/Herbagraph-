"""Canonical knowledge path intervention filtering."""

import pytest
from sqlalchemy import select

from app import database
from app.knowledge_graph.entity_registry import bootstrap_from_interventions
from app.models.canonical_entity import CanonicalEntity
from app.models.enums import KnowledgePath, PathwayDirection, RecommendationTree
from app.pipeline.canonical_graph import (
    build_interventions_for_canonical_path,
    load_registry_index,
    normalize_name,
)
from app.pipeline.knowledge_path import parse_knowledge_path
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import PathwayActivation

pytestmark = pytest.mark.unit


def test_parse_knowledge_path_defaults_and_validates():
    assert parse_knowledge_path(None) == KnowledgePath.LEGACY
    assert parse_knowledge_path("canonical") == KnowledgePath.CANONICAL
    assert parse_knowledge_path(KnowledgePath.LEGACY) == KnowledgePath.LEGACY
    with pytest.raises(ValueError):
        parse_knowledge_path("magic")


def test_normalize_name():
    assert normalize_name("  Blueberry Extract! ") == "blueberry extract"


@pytest.mark.asyncio
async def test_canonical_path_filters_to_registry(seeded_db):
    """Only interventions present in canonical_entities survive the canonical path."""
    stats = await bootstrap_from_interventions(seeded_db)
    assert stats["interventions_total"] > 0
    await seeded_db.commit()

    session_factory = database.get_sync_session_factory()
    session = session_factory()
    try:
        entity_count = len(list(session.execute(select(CanonicalEntity)).scalars().all()))
        assert entity_count > 0
        index = load_registry_index(session)
        assert index.entity_count > 0

        routing = RecommendationRoutingContext(
            trees=[RecommendationTree.NUTRITIONAL_REPLETION],
            primary_tree=RecommendationTree.NUTRITIONAL_REPLETION,
        )
        activations = [
            PathwayActivation(
                pathway_code="ONE_CARBON",
                pathway_name="One-carbon metabolism",
                activation_score=0.8,
                direction=PathwayDirection.ACTIVATED,
                contributing_biomarkers=["Vitamin B12"],
            )
        ]
        filtered, meta = build_interventions_for_canonical_path(
            routing, activations, [], session
        )
        assert meta["registry_empty"] is False
        assert meta["knowledge_path"] == "canonical"
        for names in filtered.values():
            for name in names:
                assert index.resolve(name) is not None
    finally:
        session.close()


@pytest.mark.asyncio
async def test_empty_registry_returns_empty_map(db_session):
    session_factory = database.get_sync_session_factory()
    session = session_factory()
    try:
        routing = RecommendationRoutingContext(
            trees=[RecommendationTree.SIGNALING],
            primary_tree=RecommendationTree.SIGNALING,
        )
        filtered, meta = build_interventions_for_canonical_path(routing, [], [], session)
        assert filtered == {}
        assert meta["registry_empty"] is True
    finally:
        session.close()
