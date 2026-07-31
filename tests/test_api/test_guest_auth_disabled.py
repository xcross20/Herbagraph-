"""IMP-002: registered sessions — guest auth off by default."""

import pytest

from app.config import get_settings

pytestmark = pytest.mark.asyncio


async def test_auth_config_reports_guest_disabled_by_default(client, monkeypatch):
    monkeypatch.setenv("ALLOW_GUEST_AUTH", "false")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    get_settings.cache_clear()
    resp = await client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["allow_guest_auth"] is False
    get_settings.cache_clear()


async def test_guest_registration_rejected_when_disabled(client, monkeypatch):
    monkeypatch.setenv("ALLOW_GUEST_AUTH", "false")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    monkeypatch.setenv("SIGNUP_ACCESS_CODE", "")
    get_settings.cache_clear()

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "guest-abc@guest.herbagraph-app.io",
            "password": "GuestPass1!",
            "full_name": "Guest",
        },
    )
    assert resp.status_code == 403
    assert "Guest" in resp.json()["detail"] or "registered" in resp.json()["detail"].lower()
    get_settings.cache_clear()


async def test_guest_registration_allowed_when_enabled(client, monkeypatch):
    monkeypatch.setenv("ALLOW_GUEST_AUTH", "true")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    monkeypatch.setenv("SIGNUP_ACCESS_CODE", "")
    get_settings.cache_clear()

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "guest-demo@guest.herbagraph-app.io",
            "password": "GuestPass1!",
            "full_name": "Guest",
        },
    )
    assert resp.status_code == 201
    get_settings.cache_clear()
