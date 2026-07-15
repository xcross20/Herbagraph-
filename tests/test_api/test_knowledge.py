"""Knowledge registry API."""

import pytest

from app.core.security import create_access_token, create_admin_master_token
from app.knowledge_graph.entity_registry import register_entity
from app.models.enums import CanonicalEntityType, CoverageTier, EntityReviewStatus

pytestmark = pytest.mark.asyncio


async def test_knowledge_coverage_requires_auth(client):
    resp = await client.get("/api/v1/knowledge/coverage")
    assert resp.status_code == 401


async def test_list_entities_after_register(client, db_session, test_user):
    await register_entity(
        db_session,
        canonical_name="Blueberry",
        entity_type=CanonicalEntityType.FOOD,
        coverage_tier=CoverageTier.TIER_B,
        review_status=EntityReviewStatus.MACHINE_GENERATED,
    )
    await db_session.commit()

    token = create_access_token(str(test_user.id))
    resp = await client.get(
        "/api/v1/knowledge/entities?search=Blue",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(row["canonical_name"] == "Blueberry" for row in body)


async def test_admin_enqueue_enrichment(client, db_session, test_user, master_env):
    token = create_admin_master_token()
    resp = await client.post(
        "/api/v1/knowledge/enrichment/queue",
        json={"query_name": "Amla", "priority": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["query_name"] == "Amla"