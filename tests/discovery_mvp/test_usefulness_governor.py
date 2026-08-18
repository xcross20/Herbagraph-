"""Issue 58 Slice A: pause, slots, and synthesis instead of repetitive intake."""

from __future__ import annotations

from app.discovery.orchestrator import orchestrate
from app.discovery.usefulness import (
    ControlState,
    apply_control,
    classify_control_intent,
    decide_response_mode,
    load_usefulness_fixture,
    slot_is_answered,
)


def test_pause_and_next_steps_intents():
    assert "pause_topic" in classify_control_intent("Let's not deal with the burning feet.")
    assert "request_next_steps" in classify_control_intent("What do you think I should do?")
    assert "cannot_provide_evidence" in classify_control_intent("I don't have any more labs.")
    assert "repetition_frustration" in classify_control_intent("There is a delay like I said.")


def test_pause_does_not_close_and_slots_dedupe():
    state = ControlState()
    state = apply_control(state, "For six months both of my feet have burned at night.", {"laterality": "bilateral"})
    state = apply_control(state, "Let's not deal with the burning feet.", {})
    assert state.focus["burning_feet"] == "paused_by_user"
    state = apply_control(state, "both feet again", {"laterality": "both"})
    assert state.slots["burning_feet.laterality"]["value"] == "bilateral"
    assert slot_is_answered(state, "laterality") is True


def test_explicit_next_steps_selects_synthesis_mode():
    state = ControlState(focus={"facial_heat": "active", "burning_feet": "paused_by_user"})
    state = apply_control(state, "What do you think I should do? I don't have any more labs.", {})
    mode = decide_response_mode(
        safety_state="S0",
        contradictions=[],
        control=state,
        unanswered_high_value=True,
    )
    assert mode in {"INTERIM_SYNTHESIS", "NEXT_STEPS"}


def test_fixture_transcript_does_not_reask_when_governor_enabled(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    fixture = load_usefulness_fixture()
    prior: dict[str, str] = {}
    asked: list[str] = []
    answered: set[str] = set()
    control = None
    last = None
    for turn in fixture["turns"]:
        last = orchestrate(
            turn["text"],
            prior_facts=prior,
            asked=asked,
            answered=answered,
            control_state=control,
        )
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        if last.action.question_id:
            asked.append(last.action.question_id)
            if last.action.question_id.startswith("q_"):
                answered.add(last.action.question_id)
        control = last.control
    assert last is not None
    assert last.control["focus"].get("burning_feet") == "paused_by_user"
    assert last.control["focus"].get("facial_heat") == "active"
    assert last.control["focus"].get("ruq_discomfort") == "active"
    mode = (last.action.extras or {}).get("response_mode")
    assert mode in fixture["expected"]["response_mode"]
    assert last.action.type != "ask_question"
    blob = (last.message + " " + (last.action.prompt or "")).lower()
    assert "laterality" not in blob
    assert "inflammatory" in blob
    assert "not a diagnosis" in blob
    assert "may or may not share a cause" in blob
