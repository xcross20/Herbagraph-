import pytest

pytestmark = pytest.mark.asyncio


async def test_dashboard_creates_default_self_patient(authed_client):
    resp = await authed_client.get("/api/v1/workspace/dashboard")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_email"]
    assert len(body["patients"]) >= 1
    assert body["patients"][0]["display_name"] == "Self"


async def test_create_and_update_patient(authed_client):
    create = await authed_client.post(
        "/api/v1/patients",
        json={"display_name": "Patient A", "age": 42, "biological_sex": "female"},
    )
    assert create.status_code == 201
    patient_id = create.json()["id"]
    assert create.json()["display_name"] == "Patient A"

    update = await authed_client.patch(
        f"/api/v1/patients/{patient_id}",
        json={"display_name": "Client 001", "notes": "Vegan diet"},
    )
    assert update.status_code == 200
    assert update.json()["display_name"] == "Client 001"
    assert update.json()["notes"] == "Vegan diet"


async def test_patient_context_crud(authed_client):
    patient = await authed_client.post("/api/v1/patients", json={"display_name": "Ctx Patient"})
    patient_id = patient.json()["id"]

    create = await authed_client.post(
        f"/api/v1/patients/{patient_id}/context",
        json={"context_type": "medication", "name": "Metformin", "value": "500mg"},
    )
    assert create.status_code == 201
    context_id = create.json()["id"]

    listing = await authed_client.get(f"/api/v1/patients/{patient_id}/context")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    overview = await authed_client.get(f"/api/v1/workspace/patients/{patient_id}/overview")
    assert overview.status_code == 200
    assert "Metformin" in overview.json()["context_summary"].get("medication", [])

    await authed_client.delete(f"/api/v1/patients/{patient_id}/context/{context_id}")
    listing2 = await authed_client.get(f"/api/v1/patients/{patient_id}/context")
    assert listing2.json() == []


async def test_list_analysis_sessions(authed_client):
    create = await authed_client.post(
        "/api/v1/analysis-sessions",
        json={"title": "Listed Session", "analysis_type": "multi_report_snapshot"},
    )
    assert create.status_code == 201

    resp = await authed_client.get("/api/v1/analysis-sessions")
    assert resp.status_code == 200
    titles = [s["title"] for s in resp.json()]
    assert "Listed Session" in titles