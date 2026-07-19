"""Report generation accepts knowledge_path for A/B testing."""

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


async def test_generate_accepts_canonical_knowledge_path(client, test_user, monkeypatch):
    """API accepts knowledge_path without requiring a fully processed lab."""
    token = create_access_token(str(test_user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Missing lab → 404, but body validation should not 422
    resp = await client.post(
        "/api/v1/reports/generate/00000000-0000-0000-0000-000000000001",
        headers=headers,
        json={"knowledge_path": "canonical"},
    )
    assert resp.status_code == 404

    resp_bad = await client.post(
        "/api/v1/reports/generate/00000000-0000-0000-0000-000000000001",
        headers=headers,
        json={"knowledge_path": "not-a-path"},
    )
    # Pydantic validation on enum → 422
    assert resp_bad.status_code == 422


async def test_knowledge_integrations_endpoint(client, test_user, monkeypatch):
    monkeypatch.setenv("USDA_KEY", "unit-test-usda-key")
    from app.config import get_settings

    get_settings.cache_clear()
    token = create_access_token(str(test_user.id))
    resp = await client.get(
        "/api/v1/knowledge/integrations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["usda_configured"] is True
    assert body["usda_key_present"] is True
    assert "legacy" in body["knowledge_paths"]
    assert "canonical" in body["knowledge_paths"]
    get_settings.cache_clear()
