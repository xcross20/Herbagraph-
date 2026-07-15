"""Canonical entity registry and synonym resolution."""

import pytest

from app.knowledge_graph.entity_registry import (
    bootstrap_from_interventions,
    normalize_entity_name,
    register_entity,
    resolve_entity_by_name,
)
from app.models.canonical_entity import CanonicalEntity, GraphEdge
from app.models.enums import CanonicalEntityType, CoverageTier, EntityReviewStatus
from sqlalchemy import func, select

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_register_entity_and_resolve_synonym(db_session):
    entity = await register_entity(
        db_session,
        canonical_name="Curcuma longa",
        display_name="Turmeric",
        entity_type=CanonicalEntityType.BOTANICAL,
        synonyms=["turmeric root", "haldi"],
        coverage_tier=CoverageTier.TIER_A,
        review_status=EntityReviewStatus.PRODUCTION_APPROVED,
        species="Curcuma longa",
        plant_part="rhizome",
    )
    await db_session.commit()

    assert entity.entity_id.startswith("HG-BOT-")
    resolved = await resolve_entity_by_name(db_session, "turmeric root")
    assert resolved is not None
    assert resolved.id == entity.id

    duplicate = await register_entity(
        db_session,
        canonical_name="Turmeric",
        entity_type=CanonicalEntityType.BOTANICAL,
    )
    assert duplicate.id == entity.id


def test_normalize_entity_name():
    assert normalize_entity_name("  Turmeric Root! ") == "turmeric root"


@pytest.mark.asyncio
async def test_bootstrap_from_interventions_idempotent(seeded_db):
    first = await bootstrap_from_interventions(seeded_db)
    assert first["interventions_total"] > 0
    assert first["entities_created"] > 0

    entity_count = (
        await seeded_db.execute(select(func.count()).select_from(CanonicalEntity))
    ).scalar()
    assert entity_count >= first["entities_created"]

    second = await bootstrap_from_interventions(seeded_db)
    assert second["entities_created"] == 0
    assert second["entities_skipped"] == first["interventions_total"]

    edge_count = (await seeded_db.execute(select(func.count()).select_from(GraphEdge))).scalar()
    assert edge_count >= second["composition_edges_created"]