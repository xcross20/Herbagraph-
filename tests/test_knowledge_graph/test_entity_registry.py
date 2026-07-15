"""Canonical entity registry and synonym resolution."""

import pytest

from app.knowledge_graph.entity_registry import (
    normalize_entity_name,
    register_entity,
    resolve_entity_by_name,
)
from app.models.enums import CanonicalEntityType, CoverageTier, EntityReviewStatus

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