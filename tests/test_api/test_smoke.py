import pytest

pytestmark = pytest.mark.asyncio


async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "environment" in response.json()


async def test_meta_and_demo_entry(client):
    meta = await client.get("/meta")
    assert meta.status_code == 200
    body = meta.json()
    assert body["service"] == "herbagraph"
    assert body["demo_path"] == "/demo"
    assert body["is_production"] is False
    demo = await client.get("/demo", follow_redirects=False)
    assert demo.status_code == 302
    assert demo.headers["location"] == "/app.html"


async def test_system_status_reports_auth_readiness(client):
    response = await client.get("/api/v1/system/status")
    assert response.status_code == 200
    body = response.json()
    assert "supabase_configured" in body
    assert body["jwt_verify_mode"] in {"hs256", "jwks"}
    assert "allow_guest_auth" in body
    assert "encryption_configured" in body
    assert "signup_access_required" in body


async def test_register_login_me_flow(client):
    register_resp = await client.post(
        "/api/v1/auth/register", json={"email": "jane@example.com", "password": "SecurePass1"}
    )
    assert register_resp.status_code == 201, register_resp.text
    assert register_resp.json()["email"] == "jane@example.com"

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "jane@example.com", "password": "SecurePass1"}
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]

    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "jane@example.com"


async def test_authed_client_fixture(authed_client, test_user):
    resp = await authed_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(test_user.id)


async def test_seeded_db_evidence_endpoint(authed_client, seeded_db):
    resp = await authed_client.get("/api/v1/evidence/biomarkers")
    assert resp.status_code == 200
    assert len(resp.json()) >= 200
