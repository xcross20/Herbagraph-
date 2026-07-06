import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.enums import EvidenceLevel, InterventionCategory, LabReportStatus, StudySource, StudyType
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = (
    b"CRP                    8.20  mg/L   (0.00-3.00)\n"
    b"Glucose                95.00  mg/dL   (70.00-99.00)\n"
)


def _lab_file():
    return {"file": ("labs.txt", VALID_LAB_TEXT, "text/plain")}


def _evidence_snippets():
    return [
        EvidenceSnippet(
            source=StudySource.PUBMED,
            external_id="study1",
            title="Curcumin reduces inflammatory markers: a randomized trial",
            year=2020,
            study_type=StudyType.RCT,
            quality_score=0.8,
            url="https://pubmed.ncbi.nlm.nih.gov/study1",
            abstract_snippet="Curcumin supplementation significantly reduced CRP.",
            intervention_name="Curcumin",
        ),
        EvidenceSnippet(
            source=StudySource.PUBMED,
            external_id="study2",
            title="Sulforaphane and Nrf2 activation",
            year=2016,
            study_type=StudyType.RCT,
            quality_score=0.7,
            url="https://pubmed.ncbi.nlm.nih.gov/study2",
            abstract_snippet="Sulforaphane reduced inflammatory markers.",
            intervention_name="Sulforaphane",
        ),
    ]


def _reasoning_output():
    return LLMReasoningOutput(
        biomarker_pattern_analysis="Elevated CRP suggests an active NF-kB-driven inflammatory pattern.",
        pathway_summaries=["NF-kB pathway appears activated given elevated CRP."],
        recommendations=[
            LLMRecommendation(
                intervention_name="Curcumin",
                category=InterventionCategory.HERB,
                mechanism="Inhibits NF-kB signaling, reducing downstream inflammatory cytokines.",
                evidence_level=EvidenceLevel.MODERATE,
                typical_dose="500mg twice daily",
                cited_study_ids=["study1"],
                rationale="Directly addresses the elevated CRP finding.",
            ),
            LLMRecommendation(
                intervention_name="Sulforaphane",
                category=InterventionCategory.PHYTOCHEMICAL,
                mechanism="Activates Nrf2, upregulating antioxidant response.",
                evidence_level=EvidenceLevel.MODERATE,
                typical_dose="10mg daily",
                cited_study_ids=["study2"],
                rationale="Supports antioxidant defenses relevant to inflammatory burden.",
            ),
        ],
        clinician_questions=["Has the patient had any recent infections that could elevate CRP?"],
    )


def _patch_pipeline(monkeypatch, *, evidence=None, reasoning=None):
    monkeypatch.setattr(
        "app.services.report_generation.retrieve_evidence",
        AsyncMock(return_value=evidence if evidence is not None else _evidence_snippets()),
    )
    monkeypatch.setattr(
        "app.services.report_generation.generate_reasoning",
        AsyncMock(return_value=reasoning if reasoning is not None else _reasoning_output()),
    )


async def _upload_and_complete(authed_client) -> str:
    upload_resp = await authed_client.post("/api/v1/labs/upload", files=_lab_file())
    assert upload_resp.status_code == 201
    return upload_resp.json()["lab_report_id"]


async def _start_report_generation(client, lab_report_id, headers=None):
    resp = await client.post(f"/api/v1/reports/generate/{lab_report_id}", headers=headers)
    assert resp.status_code == 202, resp.text
    return resp


async def _generate_and_fetch_report(client, lab_report_id, headers=None):
    await _start_report_generation(client, lab_report_id, headers=headers)
    for _ in range(50):
        lab_resp = await client.get(f"/api/v1/labs/{lab_report_id}", headers=headers)
        assert lab_resp.status_code == 200
        lab = lab_resp.json()
        if lab.get("report_stage") == "complete" and lab.get("latest_report_id"):
            report_resp = await client.get(f"/api/v1/reports/{lab['latest_report_id']}", headers=headers)
            assert report_resp.status_code == 200
            return report_resp
    pytest.fail("report generation did not complete in time")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


async def test_generate_report_404_for_nonexistent_lab_report(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    resp = await authed_client.post(f"/api/v1/reports/generate/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_generate_report_404_for_other_users_lab_report(client, db_session, monkeypatch):
    _patch_pipeline(monkeypatch)
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="rep-owner@example.com", hashed_password="x", is_active=True, is_verified=True)
    intruder = User(email="rep-intruder@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([owner, intruder])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=owner.id))
    db_session.add(HealthProfile(user_id=intruder.id))
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(str(intruder.id))}"}

    upload = await client.post("/api/v1/labs/upload", files=_lab_file(), headers=owner_headers)
    lab_report_id = upload.json()["lab_report_id"]

    resp = await client.post(f"/api/v1/reports/generate/{lab_report_id}", headers=intruder_headers)
    assert resp.status_code == 404


async def test_generate_report_409_if_lab_report_not_complete(authed_client, db_session, test_user, monkeypatch):
    _patch_pipeline(monkeypatch)
    from app.models.lab import LabReport

    lab_report = LabReport(
        user_id=test_user.id,
        original_filename="pending.txt",
        encrypted_file_path="",
        file_size_bytes=10,
        status=LabReportStatus.PENDING,
    )
    db_session.add(lab_report)
    await db_session.commit()
    await db_session.refresh(lab_report)

    resp = await authed_client.post(f"/api/v1/reports/generate/{lab_report.id}")
    assert resp.status_code == 409
    assert "not ready" in resp.json()["detail"].lower()


async def test_generate_report_requires_auth(client):
    resp = await client.post(f"/api/v1/reports/generate/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_generate_report_with_no_recommendations_still_201(authed_client, monkeypatch):
    _patch_pipeline(
        monkeypatch,
        evidence=[],
        reasoning=LLMReasoningOutput(
            biomarker_pattern_analysis="No supporting evidence was retrieved.",
            pathway_summaries=[],
            recommendations=[],
            clinician_questions=[],
        ),
    )
    lab_report_id = await _upload_and_complete(authed_client)

    resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    body = resp.json()
    assert body["recommendations"] == []
    assert body["citations"] == []
    assert body["clinician_questions"] == []


async def test_generate_report_calls_mocked_pipeline_functions(authed_client, monkeypatch):
    evidence_mock = AsyncMock(return_value=_evidence_snippets())
    reasoning_mock = AsyncMock(return_value=_reasoning_output())
    monkeypatch.setattr("app.services.report_generation.retrieve_evidence", evidence_mock)
    monkeypatch.setattr("app.services.report_generation.generate_reasoning", reasoning_mock)

    lab_report_id = await _upload_and_complete(authed_client)
    await _generate_and_fetch_report(authed_client, lab_report_id)

    evidence_mock.assert_awaited_once()
    reasoning_mock.assert_awaited_once()


async def test_generate_report_recommendations_have_sequential_ranks(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)
    resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    ranks = sorted(r["rank"] for r in resp.json()["recommendations"])
    assert ranks == list(range(1, len(ranks) + 1))


async def test_generate_report_twice_creates_two_distinct_reports(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)
    first = await _generate_and_fetch_report(authed_client, lab_report_id)
    second = await _generate_and_fetch_report(authed_client, lab_report_id)
    assert first.json()["id"] != second.json()["id"]

    list_resp = await authed_client.get("/api/v1/reports")
    assert len(list_resp.json()) == 2


async def test_generate_report_happy_path_full_shape(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)

    resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    body = resp.json()

    assert body["lab_report_id"] == lab_report_id
    assert "id" in body
    assert "created_at" in body
    assert isinstance(body["overall_confidence"], float)
    assert body["model_version"]
    assert body["executive_summary"]

    # biomarker_summary
    bs = body["biomarker_summary"]
    assert bs["total_biomarkers"] == 2
    assert bs["abnormal_count"] == 1
    assert bs["normal_count"] == 1
    assert isinstance(bs["categories_affected"], dict)

    # pathway_activations
    assert isinstance(body["pathway_activations"], list)
    assert len(body["pathway_activations"]) >= 1
    for activation in body["pathway_activations"]:
        assert set(["pathway_code", "pathway_name", "activation_score", "direction"]).issubset(
            activation.keys()
        )

    # recommendations
    assert len(body["recommendations"]) == 2
    names = {r["intervention_name"] for r in body["recommendations"]}
    assert names == {"Curcumin", "Sulforaphane"}
    for rec in body["recommendations"]:
        assert rec["rank"] >= 1
        assert rec["category"] in ("herb", "phytochemical")
        assert rec["evidence_level"] == "moderate"
        assert 0.0 <= rec["confidence_score"] <= 1.0
        assert rec["safety_risk"] in ("low", "moderate", "high", "contraindicated")
        assert isinstance(rec["is_regulated"], bool)

    sulforaphane_rec = next(r for r in body["recommendations"] if r["intervention_name"] == "Sulforaphane")
    assert sulforaphane_rec["food_sources"] is not None
    food_names = {fs["food"] for fs in sulforaphane_rec["food_sources"]}
    assert "Broccoli Sprouts" in food_names

    # citations
    assert len(body["citations"]) >= 1
    citation_ids = {c["id"] for c in body["citations"]}
    assert "study1" in citation_ids or "study2" in citation_ids

    # safety_summary
    ss = body["safety_summary"]
    assert "overall_note" in ss
    assert isinstance(ss["requires_clinician_review"], bool)
    assert isinstance(ss["high_risk_interventions"], list)

    assert body["disclaimer"]
    assert body["clinician_questions"] == [
        "Has the patient had any recent infections that could elevate CRP?"
    ]


# ---------------------------------------------------------------------------
# list / get / delete
# ---------------------------------------------------------------------------


async def test_list_reports_requires_auth(client):
    resp = await client.get("/api/v1/reports")
    assert resp.status_code == 401


async def test_list_reports_empty_for_new_user(authed_client):
    resp = await authed_client.get("/api/v1/reports")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_reports_only_returns_current_users_reports(client, db_session, monkeypatch):
    _patch_pipeline(monkeypatch)
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    user_a = User(email="rep-a@example.com", hashed_password="x", is_active=True, is_verified=True)
    user_b = User(email="rep-b@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([user_a, user_b])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=user_a.id))
    db_session.add(HealthProfile(user_id=user_b.id))
    await db_session.commit()

    headers_a = {"Authorization": f"Bearer {create_access_token(str(user_a.id))}"}
    headers_b = {"Authorization": f"Bearer {create_access_token(str(user_b.id))}"}

    upload_a = await client.post("/api/v1/labs/upload", files=_lab_file(), headers=headers_a)
    lab_report_id_a = upload_a.json()["lab_report_id"]
    await _generate_and_fetch_report(client, lab_report_id_a, headers=headers_a)

    list_a = await client.get("/api/v1/reports", headers=headers_a)
    assert len(list_a.json()) == 1

    list_b = await client.get("/api/v1/reports", headers=headers_b)
    assert list_b.json() == []


async def test_get_report_404_for_nonexistent_id(authed_client):
    resp = await authed_client.get(f"/api/v1/reports/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_report_404_for_other_users_report(client, db_session, monkeypatch):
    _patch_pipeline(monkeypatch)
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="repget-owner@example.com", hashed_password="x", is_active=True, is_verified=True)
    intruder = User(email="repget-intruder@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add_all([owner, intruder])
    await db_session.flush()
    db_session.add(HealthProfile(user_id=owner.id))
    db_session.add(HealthProfile(user_id=intruder.id))
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(str(intruder.id))}"}

    upload = await client.post("/api/v1/labs/upload", files=_lab_file(), headers=owner_headers)
    lab_report_id = upload.json()["lab_report_id"]
    gen = await _generate_and_fetch_report(client, lab_report_id, headers=owner_headers)
    report_id = gen.json()["id"]

    resp = await client.get(f"/api/v1/reports/{report_id}", headers=intruder_headers)
    assert resp.status_code == 404

    own_resp = await client.get(f"/api/v1/reports/{report_id}", headers=owner_headers)
    assert own_resp.status_code == 200


async def test_get_report_requires_auth(client):
    resp = await client.get(f"/api/v1/reports/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_get_report_matches_generate_response(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)
    gen_resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    report_id = gen_resp.json()["id"]

    get_resp = await authed_client.get(f"/api/v1/reports/{report_id}")
    assert get_resp.status_code == 200
    gen_body, get_body = gen_resp.json(), get_resp.json()
    # created_at may round-trip through sqlite with/without an explicit "Z" suffix depending on
    # whether it was read from the just-inserted in-memory object vs. a fresh row fetch; compare
    # everything else exactly and the timestamp as a parsed instant.
    gen_created_at, get_created_at = gen_body.pop("created_at"), get_body.pop("created_at")
    assert gen_body == get_body
    assert gen_created_at.rstrip("Z") == get_created_at.rstrip("Z")


async def test_list_reports_summary_shape_omits_recommendations(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)
    await _generate_and_fetch_report(authed_client, lab_report_id)

    resp = await authed_client.get("/api/v1/reports")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert set(body[0].keys()) == {"id", "lab_report_id", "overall_confidence", "created_at"}


async def test_delete_report_removes_it(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)
    gen = await _generate_and_fetch_report(authed_client, lab_report_id)
    report_id = gen.json()["id"]

    delete_resp = await authed_client.delete(f"/api/v1/reports/{report_id}")
    assert delete_resp.status_code == 204

    get_resp = await authed_client.get(f"/api/v1/reports/{report_id}")
    assert get_resp.status_code == 404


async def test_delete_report_404_for_nonexistent_id(authed_client):
    resp = await authed_client.delete(f"/api/v1/reports/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_delete_report_requires_auth(client):
    resp = await client.delete(f"/api/v1/reports/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# evidence tier / limitations / biomarker interpretations (Phase 1 additions)
# ---------------------------------------------------------------------------


async def test_generate_report_includes_evidence_tier_and_limitations(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)

    resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    body = resp.json()

    for rec in body["recommendations"]:
        assert rec["evidence_tier"] in (
            "established", "emerging", "preclinical", "research_hypothesis",
            "traditional_use", "historical_ethnobotanical",
        )
        assert rec["evidence_tier_label"]
        # Each mocked recommendation cites exactly one RCT -> Emerging Evidence.
        assert rec["evidence_tier"] == "emerging"
        assert rec["evidence_tier_label"] == "Emerging Evidence"
        assert "rationale" in rec
        assert "limitations" in rec


async def test_generate_report_includes_biomarker_interpretations(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)

    resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    body = resp.json()

    assert "biomarker_interpretations" in body
    interpretations = body["biomarker_interpretations"]
    assert len(interpretations) == 1
    assert interpretations[0]["biomarker_name"] == "CRP"
    assert interpretations[0]["status"] == "high"
    assert "CRP" in interpretations[0]["interpretation"]


async def test_disclaimer_supports_discussion_not_replacement(authed_client, monkeypatch):
    _patch_pipeline(monkeypatch)
    lab_report_id = await _upload_and_complete(authed_client)

    resp = await _generate_and_fetch_report(authed_client, lab_report_id)
    disclaimer = resp.json()["disclaimer"].lower()
    assert "not to replace" in disclaimer
