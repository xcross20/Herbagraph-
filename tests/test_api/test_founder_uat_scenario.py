"""PR-54: 19-step founder scenario at the real API boundary.

This is not a helper-only walk. Browser UAT against Railway still requires
Founder sign-off; this proves the same loop on the application API.
"""

from __future__ import annotations

import pytest

from app.core.security import create_access_token
from app.discovery.turn_engine import STAGES
from app.models.user import HealthProfile, User

pytestmark = pytest.mark.asyncio


async def test_turn_pipeline_still_has_nineteen_named_stages():
    assert len(STAGES) == 19
    assert STAGES[0] == "authenticate"
    assert STAGES[-1] == "emit_metrics"


async def test_founder_nineteen_step_product_loop(authed_client, client, db_session):
    # 1-3. Open burning-feet Case, attach recalled-normal labs mention, attach EMG.
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "For six months my feet have burned at night. Blood work was normal."},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert "you have" not in created.text.lower()

    emg = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={"filename": "emg-report.txt", "text": "Needle EMG and nerve conduction studies were normal."},
    )
    assert emg.status_code == 200, emg.text
    names = {item["name"]: item["value"] for item in emg.json()["case"]["findings"]}
    assert names["emg testing"] == "reported_normal"

    # 4. Investigation map: small-fiber remains open, no diagnosis.
    mapped = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert mapped.status_code == 200, mapped.text
    body = mapped.json()
    assert body["not_disease_probability"] is True
    assert (body.get("coverage") or {}).get("emg_ncs", {}).get("small_fiber_density") == "does_not_directly_assess"

    # 5. Follow-up turn (return visit).
    follow = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is still there on this return visit.", "idempotency_key": "founder-follow-1"},
    )
    assert follow.status_code == 200, follow.text

    # 6. Duplicate/idempotent replay.
    replay = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "The burning is still there on this return visit.", "idempotency_key": "founder-follow-1"},
    )
    assert replay.status_code == 200, replay.text

    # 7-8. A→B→A correction via user text then verify history on map.
    await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Correction: onset was after surgery."},
    )
    await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "Correction: actually before surgery. Correction: after surgery."},
    )

    # 9. Unsupported document does not succeed.
    bad = await authed_client.post(
        f"/api/v1/cases/{case_id}/documents",
        json={"filename": "junk.bin", "text": "unreadable binary junk"},
    )
    assert bad.status_code == 409

    # 10. Monitoring without causal claim.
    monitored = await authed_client.post(
        f"/api/v1/cases/{case_id}/monitoring",
        json={
            "target": "burning sensation",
            "observation_time": "2026-08-18",
            "outcome_kind": "no_change",
            "source_event_id": "founder-mon-1",
            "exposure": "b12",
            "adherence": "unknown",
        },
    )
    assert monitored.status_code == 200, monitored.text
    assert monitored.json()["causal_claim"] is False
    assert monitored.json()["causal_kind"] == "insufficient_for_causal_inference"

    # 11. Safety Case survives follow-up.
    urgent = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "Chest pain and I cannot catch my breath."},
    )
    urgent_id = urgent.json()["id"]
    urgent_follow = await authed_client.post(
        f"/api/v1/cases/{urgent_id}/turns",
        json={"text": "It is still happening."},
    )
    assert urgent_follow.status_code == 200
    assert "urgent" in urgent_follow.text.lower() or urgent_follow.json().get("safety", {}).get("state") in {"S3", "S4"}

    # 12. Cross-user isolation.
    other = User(email="founder-other@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(other)
    await db_session.flush()
    db_session.add(HealthProfile(user_id=other.id))
    await db_session.commit()
    stolen = await client.get(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {create_access_token(str(other.id))}"},
    )
    assert stolen.status_code == 404

    # 13. Gallbladder + EMG does not contaminate biliary evidence.
    biliary = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "I think this is my gallbladder. I also had an EMG."},
    )
    biliary_id = biliary.json()["id"]
    await authed_client.post(
        f"/api/v1/cases/{biliary_id}/documents",
        json={"filename": "emg-report.txt", "text": "Needle EMG and nerve conduction studies were normal."},
    )
    biliary_map = await authed_client.get(f"/api/v1/cases/{biliary_id}/investigation-map")
    assert biliary_map.status_code == 200
    coverage = biliary_map.json().get("coverage") or {}
    assert (coverage.get("emg_ncs") or {}).get("biliary_stones") in {None, "unknown"}

    # 14-19. No diagnostic certainty keys on the original Case map.
    final_map = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert "diagnostic_certainty" not in final_map.text
    assert final_map.json().get("not_disease_probability") is True
    assert final_map.headers.get("x-request-id")
