import pytest

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = (
    b"CRP                    8.20  mg/L   (0.00-3.00)\n"
    b"Glucose                95.00  mg/dL   (70.00-99.00)\n"
)


async def test_lab_upload_creates_audit_event(authed_client):
    resp = await authed_client.post(
        "/api/v1/labs/upload",
        files={"file": ("cbc.txt", VALID_LAB_TEXT, "text/plain")},
    )
    assert resp.status_code == 201, resp.text

    audit = await authed_client.get("/api/v1/audit")
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()]
    assert "lab_uploaded" in actions


async def test_auth_config_endpoint(client):
    resp = await client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["auth_provider"] in {"local", "supabase"}
    assert "require_email_verification" in body