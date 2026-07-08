"""API tests for report feedback, validation events, and admin dashboard."""

import os
import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.report import RecommendationReport
from app.models.validation import ReportFeedback, ValidationEvent

pytestmark = pytest.mark.asyncio


@pytest.fixture
def admin_headers(test_user, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", test_user.email)
    from app.config import get_settings

    get_settings.cache_clear()
    token = create_access_token(str(test_user.id))
    yield {"Authorization": f"Bearer {token}"}
    get_settings.cache_clear()
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)


async def _seed_report(db_session, test_user):
    report = RecommendationReport(
        lab_report_id=uuid.uuid4(),
        user_id=test_user.id,
        overall_confidence=0.8,
        model_version="test",
        executive_summary="Test summary",
        biomarker_summary={
            "total_biomarkers": 1,
            "abnormal_count": 1,
            "measured_biomarkers": [{"biomarker_name": "Iron", "status": "low"}],
        },
        pathway_activations=[{"pathway_code": "IRON_HEPCIDIN", "activation_score": 0.7}],
        biological_systems=[{"system_code": "nutrient_status", "system_name": "Nutrient Status", "signal_level": 2}],
        clinician_questions=[],
        safety_summary={"overall_note": "", "requires_clinician_review": False, "high_risk_interventions": []},
        disclaimer="Not medical advice.",
        report_insights={
            "missing_information": {"suggested_biomarkers": ["Ferritin"]},
            "overall_confidence_assessment": {"confidence_label": "High"},
        },
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


async def test_submit_report_feedback_and_track_event(authed_client, db_session, test_user):
    report = await _seed_report(db_session, test_user)
    response = await authed_client.post(
        f"/api/v1/reports/{report.id}/report-feedback",
        json={
            "clinical_usefulness_score": 5,
            "reasoning_agreement": "completely",
            "patient_encounter_comfort": "yes_minor_edits",
            "estimated_time_saved_bucket": "10_20",
            "free_text_feedback": "Excellent evidence.",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["clinical_usefulness_score"] == 5
    assert body["trust_score"] == 4
    assert body["estimated_time_saved_minutes"] == 15

    events = await db_session.execute(select(ValidationEvent).where(ValidationEvent.report_id == report.id))
    assert events.scalars().first() is not None


async def test_track_validation_event(authed_client, db_session, test_user):
    report = await _seed_report(db_session, test_user)
    response = await authed_client.post(
        "/api/v1/validation/events",
        json={
            "report_id": str(report.id),
            "event_type": "opened_evidence_passport",
            "section_name": "evidence_passport",
        },
    )
    assert response.status_code == 201
    assert response.json()["event_type"] == "opened_evidence_passport"


async def test_admin_dashboard_requires_admin_email(authed_client):
    os.environ.pop("ADMIN_EMAILS", None)
    from app.config import get_settings

    get_settings.cache_clear()
    response = await authed_client.get("/api/v1/admin/validation/dashboard")
    assert response.status_code == 403
    get_settings.cache_clear()


async def test_admin_dashboard_aggregates_feedback(admin_headers, authed_client, db_session, test_user):
    report = await _seed_report(db_session, test_user)
    db_session.add(
        ReportFeedback(
            report_id=report.id,
            user_id=test_user.id,
            clinical_usefulness_score=5,
            reasoning_agreement="completely",
            trust_score=5,
            estimated_time_saved_minutes=18,
            patient_encounter_comfort="yes",
            would_use_again="yes",
            free_text_feedback="Excellent evidence.",
        )
    )
    await db_session.commit()

    authed_client.headers.update(admin_headers)
    response = await authed_client.get("/api/v1/admin/validation/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["reports_reviewed"] >= 1
    assert body["average_usefulness_score"] == 5.0
    assert body["average_trust_score"] == 5.0
    assert body["free_text_feedback"]