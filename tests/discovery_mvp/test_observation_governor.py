"""Issue 58: novel observations persist and repetition complaints stop re-asks."""

from __future__ import annotations

import json
from pathlib import Path

from app.discovery.intake import extract_facts, fact_map, facts_to_findings
from app.discovery.observations import extract_observations, merge_observations
from app.discovery.orchestrator import orchestrate
from app.discovery.usefulness import classify_control_intent


def test_reproductive_area_is_not_epigastric():
    facts = extract_facts("itchy crawling in the reproductive area and under the right ribs")
    mapped = fact_map(facts_to_findings(facts))
    assert mapped.get("location") != "epigastric"
    assert mapped.get("location") == "ruq"
    assert mapped.get("itch_site") == "reproductive_or_genital_area"
    obs = extract_observations("itchy crawling in the reproductive area")
    assert any(item["site"] == "genital_or_reproductive_area" for item in obs)
    assert all(item["site"] != "epigastric" for item in obs)


def test_negatives_close_swelling_and_redness_slots(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    result = orchestrate(
        "No swelling, redness, or warmth.",
        prior_facts={"location": "ruq"},
        asked=[],
        answered=set(),
    )
    slots = result.control["slots"]
    assert slots.get("case.swelling", {}).get("value") == "absent"
    assert slots.get("case.redness", {}).get("value") == "absent"


def test_why_show_evidence_and_repeat_complaint_force_synthesis(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    assert "request_research" in classify_control_intent("why? show evidence")
    assert "repetition_frustration" in classify_control_intent("you've asked the same thing multiple times.")
    prior = {"location": "ruq"}
    control = None
    last = None
    fixture = json.loads(
        (Path("benchmarks/discovery_usefulness/v1/repeat_complaint.json")).read_text(encoding="utf-8")
    )
    for turn in fixture["turns"]:
        last = orchestrate(turn["text"], prior_facts=prior, asked=[], answered=set(), control_state=control)
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        control = last.control
    extras = last.action.extras or {}
    assert extras.get("response_mode") in {"INTERIM_SYNTHESIS", "NEXT_STEPS", "RESEARCH_EXPLANATION"}
    assert last.action.type != "ask_question"
    blob = (last.message + " " + (last.action.prompt or "")).lower()
    assert "asked a closed question" in blob or "will not ask" in blob
    assert "crawling" in blob or "itch" in blob
    assert "reproductive" in blob or "genital" in blob
    assert "does not establish inflammation" in blob
    assert "felt at epigastric" not in blob
    assert "?" not in last.action.prompt or "swelling" not in blob
    codes = {item.get("phenomenon") for item in (last.control.get("observations") or [])}
    assert "crawling_sensation" in codes or "itch" in codes
    replay = merge_observations(last.control["observations"], extract_observations(fixture["turns"][2]["text"]))
    assert len(replay) == len(last.control["observations"])
