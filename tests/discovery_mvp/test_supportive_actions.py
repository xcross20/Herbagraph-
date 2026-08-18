"""Issue 64 / #58: relief intent selects SUPPORTIVE_ACTIONS, not another question."""

from __future__ import annotations

import json
from pathlib import Path

from app.discovery.orchestrator import orchestrate
from app.discovery.supportive_actions import build_action_plan
from app.discovery.usefulness import classify_control_intent


def test_relief_phrases_select_supportive_intent():
    assert "request_supportive_actions" in classify_control_intent(
        "yeah after fatty foods, ive been wondering if theres any thing i can do for relief before getting some of these tests"
    )
    assert "request_supportive_actions" in classify_control_intent("yeah possibly but what can i do now?")


def test_relief_transcript_does_not_ask_another_question(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    fixture = json.loads(Path("benchmarks/discovery_usefulness/v1/relief_now.json").read_text(encoding="utf-8"))
    prior = {}
    control = None
    last = None
    for turn in fixture["turns"]:
        last = orchestrate(turn["text"], prior_facts=prior, asked=[], answered=set(), control_state=control)
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        control = last.control
    extras = last.action.extras or {}
    assert extras.get("response_mode") == "SUPPORTIVE_ACTIONS"
    assert last.action.type != "ask_question"
    blob = (last.message + " " + (last.action.prompt or "")).lower()
    assert "would you be open to discussing hida" not in blob
    assert "low-risk options now" in blob
    assert "bile" in blob or "supplement" in blob
    assert extras.get("action_plan")
    assert extras.get("snapshot_id")
    assert extras.get("family_ids")
    assert extras["action_plan"]["snapshot_id"] == extras["snapshot_id"]
    assert extras["action_plan"]["supplements_eligible"] is False
    ids = {item["id"] for item in extras["action_plan"]["options"]}
    assert "sa-avoid-reported-fat-trigger" in ids


def test_commerce_cannot_enter_supportive_plan():
    plan = build_action_plan(
        control=None,
        facts={"location": "ruq", "fatty_food": "triggers"},
        safety_state="S0",
        family_ids=["biliary_colic_pattern"],
        snapshot_id="snap-1",
    )
    assert all(item.get("commerce_neutral") is True for item in plan["options"])
    assert plan["supplements_eligible"] is False
    assert not any("magnesium" in (item.get("label") or "").lower() for item in plan["options"])
