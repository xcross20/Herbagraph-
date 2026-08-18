"""Issue 58 Slice D: API walk of the synthetic usefulness fixture."""

from __future__ import annotations

import pytest

from app.discovery.usefulness import load_usefulness_fixture

pytestmark = pytest.mark.asyncio


async def test_issue_58_fixture_api_walk_does_not_reask(authed_client, monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    fixture = load_usefulness_fixture()
    first = fixture["turns"][0]["text"]
    created = await authed_client.post("/api/v1/cases", json={"presenting_concern": first})
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    last = created
    for index, turn in enumerate(fixture["turns"][1:], start=2):
        last = await authed_client.post(
            f"/api/v1/cases/{case_id}/turns",
            json={"text": turn["text"], "idempotency_key": f"use-58-{index}"},
        )
        assert last.status_code == 200, last.text
    body = last.json()
    replay = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": fixture["turns"][-1]["text"], "idempotency_key": "use-58-last"},
    )
    assert replay.status_code == 200, replay.text
    control = body.get("control") or {}
    turn_state = body.get("turn_state") or {}
    action = (turn_state.get("selected_action") or {})
    reply = " ".join(
        part
        for part in (
            action.get("prompt"),
            action.get("objective"),
            body.get("problem_representation"),
        )
        if part
    ).lower()
    assert control.get("focus", {}).get("burning_feet") == "paused_by_user"
    assert action.get("type") != "ask_question" or action.get("question_id") != "q_laterality"
    assert "you have" not in reply
    assert "not a diagnosis" in (last.text or "").lower() or (body.get("disclaimer") or "")
    assert turn_state.get("response_mode") in {None, "INTERIM_SYNTHESIS", "NEXT_STEPS", "ASK_ONE_QUESTION", "SAFETY_ESCALATION"}
    safety = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "I suddenly cannot lift my foot.", "idempotency_key": "use-58-safety"},
    )
    assert safety.status_code == 200, safety.text
    assert "urgent" in safety.text.lower() or (safety.json().get("safety") or {}).get("state") in {"S3", "S4"}
