"""Tests that the bare-bones static frontend (frontend/index.html) is served at "/"
without shadowing any API routes."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_root_serves_frontend_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "HerbaGraph" in resp.text
    assert "Analyze" in resp.text


async def test_api_routes_still_work_alongside_static_mount(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_unknown_path_falls_back_to_404_not_swallowed_by_static_mount(client):
    resp = await client.get("/this-path-does-not-exist-anywhere")
    assert resp.status_code == 404
