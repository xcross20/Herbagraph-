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


async def test_dashboard_with_string_executive_summary(authed_client, db_session, test_user):
    from app.models.lab import LabReport
    from app.models.enums import LabReportStatus
    from app.models.report import RecommendationReport

    lab = LabReport(
        user_id=test_user.id,
        original_filename="summary_test.txt",
        encrypted_file_path="enc",
        file_size_bytes=10,
        status=LabReportStatus.COMPLETE,
    )
    db_session.add(lab)
    await db_session.flush()
    report = RecommendationReport(
        lab_report_id=lab.id,
        user_id=test_user.id,
        overall_confidence=0.9,
        model_version="1.0.0",
        executive_summary="Integrated from 3 lab reports. This patient presents with iron deficiency.",
        biomarker_summary={},
        biomarker_interpretations=[],
        pathway_activations=[],
        biological_systems=[],
        clinician_questions=[],
        safety_summary={},
        medication_context={},
        lab_trends={},
        disclaimer="Test disclaimer",
    )
    db_session.add(report)
    await db_session.commit()

    resp = await authed_client.get("/api/v1/workspace/dashboard")
    assert resp.status_code == 200, resp.text
    titles = [r["title"] for r in resp.json()["recent_reports"]]
    assert any("iron deficiency" in t for t in titles)


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


# ── Personal Evidence: Regimen Truth Slice 1 ────────────────────────────────

async def test_dashboard_returns_feature_flags_field(authed_client):
    """The dashboard response must include a feature_flags dict so the frontend
    can gate the Regimen Truth module without a separate round-trip."""
    resp = await authed_client.get("/api/v1/workspace/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "feature_flags" in body, "feature_flags key must be present"
    assert isinstance(body["feature_flags"], dict), "feature_flags must be a dict"


async def test_feature_flag_off_by_default(authed_client):
    """PERSONAL_EVIDENCE_REGIMEN_V1 must be False unless explicitly enabled,
    so the Regimen module does not silently appear in production."""
    resp = await authed_client.get("/api/v1/workspace/dashboard")
    assert resp.status_code == 200
    flags = resp.json()["feature_flags"]
    # Explicitly False or absent — both are safe; neither activates the module.
    regimen_flag = flags.get("personal_evidence_regimen_v1", False)
    assert regimen_flag is False, (
        "personal_evidence_regimen_v1 should be False by default; "
        "do not enable in production unless intentionally toggled"
    )


async def test_feature_flag_key_is_snake_case(authed_client):
    """The flag key must be snake_case so it matches the Python config name
    and avoids camelCase inconsistencies between config and API response."""
    resp = await authed_client.get("/api/v1/workspace/dashboard")
    assert resp.status_code == 200
    for key in resp.json()["feature_flags"]:
        assert "_" in key or key.islower(), (
            f"Feature flag key '{key}' should be snake_case (e.g., personal_evidence_regimen_v1)"
        )


async def test_case_overview_flag_off_by_default(authed_client):
    """CASE_OVERVIEW_V1 must be False unless explicitly enabled, protecting
    the My Case surface from accidental production exposure."""
    resp = await authed_client.get("/api/v1/workspace/dashboard")
    assert resp.status_code == 200
    flags = resp.json()["feature_flags"]
    co_flag = flags.get("case_overview_v1", False)
    assert co_flag is False, (
        "case_overview_v1 should be False by default; "
        "do not enable in production unless intentionally toggled"
    )


async def test_case_overview_api_returns_403_by_default(authed_client):
    """The /cases/{id}/overview endpoint must return 403 when the flag is off."""
    # Create a case
    case_resp = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "Test case for 403"},
    )
    assert case_resp.status_code == 201
    case_id = case_resp.json()["id"]

    # Overview must be 403 with flag off
    overview_resp = await authed_client.get(f"/api/v1/cases/{case_id}/overview")
    assert overview_resp.status_code == 403, (
        "case_overview_v1 off → 403, not " + str(overview_resp.status_code)
    )
    body = overview_resp.json()
    assert "not enabled" in (body.get("detail") or "").lower()