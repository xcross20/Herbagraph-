"""Issue 58 Slice D: paraphrase, hostile citation, commerce, and PHI certification."""

from __future__ import annotations

import json

from app.discovery.claim_cards import build_claim_card
from app.discovery.decision_events import hashed_source
from app.discovery.next_evidence import candidates_for_control, plan_next_evidence
from app.discovery.orchestrator import orchestrate
from app.discovery.ranker import rank_next_actions
from app.discovery.telemetry import increment, reset, snapshot
from app.discovery.tripwires import ZERO_TRIPWIRES
from app.discovery.usefulness import (
    ControlState,
    apply_control,
    classify_control_intent,
    decide_response_mode,
    filter_paused_questions,
    slot_is_answered,
)


def test_paraphrases_map_to_one_slot():
    state = ControlState()
    state = apply_control(state, "It lasts an hour or two.", {})
    first = state.slots["facial_heat.duration"]["value"]
    state = apply_control(state, "It lasts about 60–120 minutes.", {})
    assert state.slots["facial_heat.duration"]["value"] == first
    state = apply_control(state, "It starts an hour or more after eating.", {})
    assert slot_is_answered(state, "meal_relation") is True
    state = apply_control(state, "Both feet burn.", {"laterality": "both"})
    state = apply_control(state, "both feet again", {"laterality": "both feet"})
    assert state.slots["burning_feet.laterality"]["value"] == "bilateral"


def test_pause_and_no_labs_paraphrases_drive_control():
    assert "pause_topic" in classify_control_intent("I don't want to talk about the feet.")
    assert "cannot_provide_evidence" in classify_control_intent("I don't have those labs.")
    state = apply_control(ControlState(), "I don't have those labs.", {})
    assert state.slots["prior_labs.records_available"]["value"] == "false"
    mode = decide_response_mode(
        safety_state="S0",
        contradictions=[],
        control=apply_control(ControlState(focus={"facial_heat": "active"}), "What should I do?", {}),
        unanswered_high_value=True,
    )
    assert mode in {"NEXT_STEPS", "INTERIM_SYNTHESIS"}


def test_safety_overrides_paused_branch():
    state = ControlState(focus={"burning_feet": "paused_by_user"})
    assert filter_paused_questions("show_safety_message", None, "cannot lift my foot", state) is False
    mode = decide_response_mode(
        safety_state="S4",
        contradictions=[],
        control=state,
        unanswered_high_value=True,
    )
    assert mode == "SAFETY_ESCALATION"


def test_commerce_cannot_change_scientific_rank():
    state = ControlState(focus={"facial_heat": "active"})
    rows = candidates_for_control(state)
    assert rows
    assert all(item.get("commerce_boosted") is False for item in rows)
    cheap = dict(rows[0], code="cheap", commerce_boosted=False, information_value=0.7)
    expensive = dict(rows[0], code="gold-label", commerce_boosted=True, information_value=0.99)
    ranked = rank_next_actions(gaps=[cheap, expensive], safety_level="S0")
    assert ranked
    assert ranked[0].gap_code != "gold-label"
    assert "commerce_changed_scientific_rank" in ZERO_TRIPWIRES


def test_fabricated_pmid_and_irrelevant_source_fail_closed():
    fabricated = build_claim_card(statement="This proves a diagnosis.", source_id="pmid:00000000")
    assert fabricated["accepted"] is False
    missing = build_claim_card(statement="A paper exists.", source_id="doi:not-real")
    assert missing["accepted"] is False


def test_decision_log_and_telemetry_have_no_raw_health_text(monkeypatch):
    reset()
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    last = orchestrate(
        "Let's not deal with the burning feet. What do you think I should do? I don't have any more labs.",
        prior_facts={"laterality": "bilateral"},
        asked=["q_laterality"],
        answered={"laterality"},
        control_state={
            "focus": {"burning_feet": "paused_by_user", "facial_heat": "active", "ruq_discomfort": "active"},
            "slots": {"burning_feet.laterality": {"status": "answered", "value": "bilateral"}},
        },
    )
    payload = json.dumps(last.control)
    assert "what do you think i should do" not in payload.lower()
    assert "i don't have any more labs" not in payload.lower()
    log = last.control.get("decision_log") or {}
    identities = [item.get("source_event_id") for item in log.get("events") or []]
    assert identities
    assert all(event_id != last.message for event_id in identities)
    assert all(len(str(event_id)) == 24 for event_id in identities)
    increment("phi_key_ssn")
    counts = snapshot()
    assert "phi_key_ssn" not in counts
    assert counts.get("phi_key_rejected", 0) >= 1
    assert "phi_in_telemetry" in ZERO_TRIPWIRES


def test_planner_skips_paused_and_emg_non_addressing():
    state = ControlState(focus={"burning_feet": "paused_by_user", "facial_heat": "active"})
    planned = plan_next_evidence(state)
    labels = " ".join(item["label"].lower() for item in planned)
    assert "emg" not in labels
    assert not any(str(item.get("id") or "").startswith("bf-") for item in planned)
