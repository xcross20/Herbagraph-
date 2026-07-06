"""Tests for app.core.auth_providers: the Phase 3 pluggable-auth abstraction.

Only the "local" path (existing JWT/bcrypt auth) is actually implemented and is
covered thoroughly elsewhere (test_security.py, test_auth.py). These tests cover
the "clerk"/"firebase" stub behavior: unconfigured -> clear config error;
configured-but-unimplemented -> clear "not implemented" error. Neither path is
ever exercised by default since settings.auth_provider defaults to "local".
"""

import pytest

from app.core.auth_providers import AuthConfigurationError, verify_external_token

pytestmark = pytest.mark.asyncio


async def test_clerk_without_secret_key_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("app.core.auth_providers.settings.auth_provider", "clerk")
    monkeypatch.setattr("app.core.auth_providers.settings.clerk_secret_key", "")
    with pytest.raises(AuthConfigurationError, match="CLERK_SECRET_KEY"):
        await verify_external_token("some-token")


async def test_clerk_with_secret_key_raises_not_implemented(monkeypatch):
    monkeypatch.setattr("app.core.auth_providers.settings.auth_provider", "clerk")
    monkeypatch.setattr("app.core.auth_providers.settings.clerk_secret_key", "sk_test_123")
    with pytest.raises(AuthConfigurationError, match="not implemented"):
        await verify_external_token("some-token")


async def test_firebase_without_project_id_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("app.core.auth_providers.settings.auth_provider", "firebase")
    monkeypatch.setattr("app.core.auth_providers.settings.firebase_project_id", "")
    with pytest.raises(AuthConfigurationError, match="FIREBASE_PROJECT_ID"):
        await verify_external_token("some-token")


async def test_firebase_with_project_id_raises_not_implemented(monkeypatch):
    monkeypatch.setattr("app.core.auth_providers.settings.auth_provider", "firebase")
    monkeypatch.setattr("app.core.auth_providers.settings.firebase_project_id", "my-project")
    with pytest.raises(AuthConfigurationError, match="not implemented"):
        await verify_external_token("some-token")


async def test_unknown_provider_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("app.core.auth_providers.settings.auth_provider", "okta")
    with pytest.raises(AuthConfigurationError, match="Unknown AUTH_PROVIDER"):
        await verify_external_token("some-token")


async def test_get_current_user_501s_when_non_local_provider_selected(client, monkeypatch, auth_headers):
    monkeypatch.setattr("app.api.deps.settings.auth_provider", "clerk")
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 501
    assert "CLERK_SECRET_KEY" in resp.json()["detail"]
