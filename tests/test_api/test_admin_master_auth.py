"""Admin master password gate."""

import pytest

from app.core.security import create_admin_master_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
def master_env(monkeypatch, test_user):
    monkeypatch.setenv("ADMIN_MASTER_PASSWORD", "MasterPass123!")
    monkeypatch.setenv("ADMIN_EMAILS", test_user.email)
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    monkeypatch.delenv("ADMIN_MASTER_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)


async def test_master_login_rejects_wrong_password(client, master_env):
    resp = await client.post("/api/v1/admin/master-login", json={"password": "wrong-password"})
    assert resp.status_code == 401


async def test_master_login_returns_token(client, master_env):
    resp = await client.post("/api/v1/admin/master-login", json={"password": "MasterPass123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["admin_token"]
    assert body["token_type"] == "bearer"


async def test_master_token_grants_admin_api(client, master_env, db_session, test_user):
    token = create_admin_master_token()
    resp = await client.get("/api/v1/admin/users?limit=5", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_master_login_unconfigured_returns_503(client, monkeypatch):
    monkeypatch.delenv("ADMIN_MASTER_PASSWORD", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    resp = await client.post("/api/v1/admin/master-login", json={"password": "MasterPass123!"})
    assert resp.status_code == 503
    get_settings.cache_clear()