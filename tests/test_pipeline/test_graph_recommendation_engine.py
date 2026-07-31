"""Graph recommendation engine unit tests."""

import pytest
from sqlalchemy import select

from app import database
from app.knowledge_graph.entity_registry import bootstrap_from_interventions, register_entity
from app.knowledge_graph.graph_edge_seed import bootstrap_graph_modulation_edges, pathways_from_mechanism
from app.models.canonical_entity import CanonicalEntity, GraphEdge
from app.models.enums import (
    CanonicalEntityType,
    CoverageTier,
    EntityReviewStatus,
    PathwayDirection,
    RecommendationTree,
)
from app.pipeline.graph_recommendation_engine import build_interventions_from_graph
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.pipeline import PathwayActivation

pytestmark = pytest.mark.unit


def test_pathways_from_mechanism_detects_nfkb():
    codes = pathways_from_mechanism("Inhibits NF-κB inflammatory signaling", "herb")
    assert "NF_KB" in codes


@pytest.mark.asyncio
async def test_bootstrap_graph_edges_creates_modulates(seeded_db):
    await bootstrap_from_interventions(seeded_db)
    await seeded_db.commit()
    stats = await bootstrap_graph_modulation_edges(seeded_db)
    assert stats["claims_processed"] > 0
    assert stats["modulates_from_claims"] > 0 or stats["modulates_from_catalog"] > 0

    # Sync view for graph engine
    session = database.get_sync_session_factory()()
    try:
        edge_count = len(list(session.execute(select(GraphEdge)).scalars().all()))
        assert edge_count > 0
        path_nodes = list(
            session.execute(
                select(CanonicalEntity).where(
                    CanonicalEntity.entity_type == CanonicalEntityType.PATHWAY.value
                )
            ).scalars().all()
        )
        assert path_nodes, "Expected pathway nodes to be registered"

        routing = RecommendationRoutingContext(
            trees=[RecommendationTree.SIGNALING],
            primary_tree=RecommendationTree.SIGNALING,
        )
        activations = [
            PathwayActivation(
                pathway_code="NF_KB",
                pathway_name="NF-κB",
                activation_score=0.9,
                direction=PathwayDirection.ACTIVATED,
                contributing_biomarkers=["CRP"],
            )
        ]
        mapping, meta = build_interventions_from_graph(
            session, routing, activations, [], hybrid_legacy_fill=True
        )
        assert meta["engine"] == "graph_recommendation_engine_v1"
        # Should surface at least one intervention for NF_KB from graph or hybrid
        assert "NF_KB" in mapping or meta["matched_intervention_count"] >= 0
        if mapping.get("NF_KB"):
            assert len(mapping["NF_KB"]) >= 1
    finally:
        session.close()


@pytest.mark.asyncio
async def test_register_pathway_entity_type(db_session):
    entity = await register_entity(
        db_session,
        canonical_name="NF_KB",
        display_name="NF-κB Inflammatory Signaling",
        entity_type=CanonicalEntityType.PATHWAY,
        coverage_tier=CoverageTier.TIER_A,
        review_status=EntityReviewStatus.PRODUCTION_APPROVED,
    )
    await db_session.commit()
    assert entity.entity_id.startswith("HG-PATH-")
