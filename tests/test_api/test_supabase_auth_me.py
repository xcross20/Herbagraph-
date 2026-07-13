"""Supabase-authenticated /auth/me and user provisioning."""

import time
import uuid

import pytest
from jose import jwt

from app.config import Settings

def _supabase_token(*, email: str = "clinician@example.com", sub: str | None = None) -> str:
    now = int(time.time())
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "email_verified": True,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-supabase-jwt-secret-32chars!!", algorithm="HS256")


@pytest.fixture
def supabase_env(monkeypatch):
    monkeypatch.setattr("app.api.deps.settings.auth_provider", "supabase")
    monkeypatch.setattr("app.api.deps.settings.supabase_url", "https://example.supabase.co")
    monkeypatch.setattr("app.api.deps.settings.supabase_jwt_secret", "test-supabase-jwt-secret-32chars!!")
    monkeypatch.setattr("app.api.deps.settings.require_email_verification", False)
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_url", "https://example.supabase.co")
    monkeypatch.setattr("app.core.supabase_auth.settings.supabase_jwt_secret", "test-supabase-jwt-secret-32chars!!")
    monkeypatch.setattr("app.core.auth_providers.settings.auth_provider", "supabase")
    monkeypatch.setattr("app.api.v1.auth.settings.auth_provider", "supabase")


@pytest.mark.asyncio
async def test_auth_me_provisions_supabase_user(client, supabase_env):
    token = _supabase_token(email=f"new-{uuid.uuid4().hex[:8]}@example.com")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["auth_provider"] == "supabase"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_auth_sync_provisions_supabase_user(client, supabase_env):
    email = f"sync-{uuid.uuid4().hex[:8]}@example.com"
    token = _supabase_token(email=email)
    resp = await client.post("/api/v1/auth/sync", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email


def test_database_url_normalizes_railway_postgres_url():
    settings = Settings(database_url="postgresql://user:pass@host:5432/railway")
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/railway"