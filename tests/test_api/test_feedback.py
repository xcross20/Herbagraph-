"""Tests for the Feedback model/API (Phase 4 infrastructure)."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.enums import EvidenceLevel, InterventionCategory
from app.schemas.pipeline import EvidenceSnippet, LLMReasoningOutput, LLMRecommendation
from app.models.enums import StudySource, StudyType

pytestmark = pytest.mark.asyncio

VALID_LAB_TEXT = b"CRP                    8.20  mg/L   (0.00-3.00)\n"


def _patch_pipeline(monkeypatch):
    evidence = [
        EvidenceSnippet(
            source=StudySource.PUBMED,
            external_id="study1",
            title="Curcumin reduces inflammatory markers",
            year=2020,
            study_type=StudyType.RCT,
            quality_score=0.8,
            url="https://pubmed.ncbi.nlm.nih.gov/study1",
            intervention_name="Curcumin",
        )
    ]
    reasoning = LLMReasoningOutput(
        biomarker_pattern_analysis="Elevated CRP.",
        recommendations=[
            LLMRecommendation(
                intervention_name="Curcumin",
                category=InterventionCategory.HERB,
                mechanism="Inhibits NF-kB.",
                evidence_level=EvidenceLevel.MODERATE,
                cited_study_ids=["study1"],
            )
        ],
    )
    monkeypatch.setattr("app.services.report_generation.retrieve_evidence", AsyncMock(return_value=evidence))
    monkeypatch.setattr("app.services.report_generation.generate_reasoning", AsyncMock(return_value=reasoning))


async def _create_report(authed_client, monkeypatch) -> str:
    _patch_pipeline(monkeypatch)
    upload_resp = await authed_client.post(
        "/api/v1/labs/upload", files={"file": ("labs.txt", VALID_LAB_TEXT, "text/plain")}
    )
    lab_report_id = upload_resp.json()["lab_report_id"]
    gen_resp = await authed_client.post(f"/api/v1/reports/generate/{lab_report_id}")
    assert gen_resp.status_code == 202, gen_resp.text
    for _ in range(50):
        lab_resp = await authed_client.get(f"/api/v1/labs/{lab_report_id}")
        lab = lab_resp.json()
        if lab.get("report_stage") == "complete" and lab.get("latest_report_id"):
            return lab["latest_report_id"]
    pytest.fail("report generation did not complete in time")


async def test_submit_feedback_happy_path(authed_client, monkeypatch):
    report_id = await _create_report(authed_client, monkeypatch)
    resp = await authed_client.post(
        f"/api/v1/reports/{report_id}/feedback", json={"rating": 4, "comment": "Helpful."}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["rating"] == 4
    assert body["comment"] == "Helpful."
    assert body["report_id"] == report_id


async def test_submit_feedback_without_comment(authed_client, monkeypatch):
    report_id = await _create_report(authed_client, monkeypatch)
    resp = await authed_client.post(f"/api/v1/reports/{report_id}/feedback", json={"rating": 5})
    assert resp.status_code == 201, resp.text
    assert resp.json()["comment"] is None


@pytest.mark.parametrize("rating", [0, 6, -1])
async def test_submit_feedback_rejects_out_of_range_rating(authed_client, monkeypatch, rating):
    report_id = await _create_report(authed_client, monkeypatch)
    resp = await authed_client.post(f"/api/v1/reports/{report_id}/feedback", json={"rating": rating})
    assert resp.status_code == 422


async def test_submit_feedback_404_for_nonexistent_report(authed_client):
    resp = await authed_client.post(f"/api/v1/reports/{uuid.uuid4()}/feedback", json={"rating": 3})
    assert resp.status_code == 404


async def test_submit_feedback_requires_auth(client):
    resp = await client.post(f"/api/v1/reports/{uuid.uuid4()}/feedback", json={"rating": 3})
    assert resp.status_code == 401


async def test_list_feedback_returns_submitted_entries(authed_client, monkeypatch):
    report_id = await _create_report(authed_client, monkeypatch)
    await authed_client.post(f"/api/v1/reports/{report_id}/feedback", json={"rating": 4})
    await authed_client.post(f"/api/v1/reports/{report_id}/feedback", json={"rating": 2, "comment": "Meh"})

    resp = await authed_client.get(f"/api/v1/reports/{report_id}/feedback")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_feedback_404_for_other_users_report(client, db_session, monkeypatch):
    from app.core.security import create_access_token
    from app.models.user import HealthProfile, User

    owner = User(email="owner2@example.com", hashed_password="x")
    intruder = User(email="intruder2@example.com", hashed_password="x")
    db_session.add_all([owner, intruder])
    await db_session.flush()
    db_session.add_all([HealthProfile(user_id=owner.id), HealthProfile(user_id=intruder.id)])
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(str(intruder.id))}"}

    _patch_pipeline(monkeypatch)
    client.headers.update(owner_headers)
    upload_resp = await client.post(
        "/api/v1/labs/upload", files={"file": ("labs.txt", VALID_LAB_TEXT, "text/plain")}
    )
    lab_report_id = upload_resp.json()["lab_report_id"]
    gen_resp = await client.post(f"/api/v1/reports/generate/{lab_report_id}")
    assert gen_resp.status_code == 202, gen_resp.text
    report_id = None
    for _ in range(50):
        lab_resp = await client.get(f"/api/v1/labs/{lab_report_id}")
        lab = lab_resp.json()
        if lab.get("report_stage") == "complete" and lab.get("latest_report_id"):
            report_id = lab["latest_report_id"]
            break
    assert report_id is not None
    client.headers.pop("Authorization")

    resp = await client.get(f"/api/v1/reports/{report_id}/feedback", headers=intruder_headers)
    assert resp.status_code == 404
