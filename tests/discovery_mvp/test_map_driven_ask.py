"""Issue 58/61 UAT: Ask must consume the same explanation view as the panel."""

from __future__ import annotations

from app.discovery.catalog import HYPOTHESIS_FAMILIES
from app.discovery.explanation import build_explanation_view
from app.discovery.map import confidence_increasers
from app.discovery.orchestrator import orchestrate
from app.discovery.usefulness import classify_control_intent, usefulness_governor_enabled


def test_uat_forces_governor_even_if_flag_is_off(monkeypatch):
    monkeypatch.setattr("app.config.get_settings", lambda: type("S", (), {"app_env": "uat", "discovery_usefulness_governor_v1": False})())
    assert usefulness_governor_enabled() is True


def test_answers_now_and_other_insight_select_synthesis():
    assert "request_synthesis" in classify_control_intent("I want answers now")
    assert "request_next_steps" in classify_control_intent("is there any other insight")


def test_labels_do_not_overstate_unevaluated_gaps():
    labels = {item.code: item.label for item in HYPOTHESIS_FAMILIES}
    assert labels["b12_functional_gap"] == "B12/one-carbon status not fully evaluated"
    assert labels["glucose_dysregulation"] == "Glucose regulation not yet evaluated"
    small = next(item for item in HYPOTHESIS_FAMILIES if item.code == "small_fiber_dysfunction")
    assert "Vitamin B12" not in small.core
    assert "confirmatory" not in small.why_not_a_diagnosis.lower()


def test_glucose_confidence_rows_are_unique():
    class _Hypo:
        label = "Glucose regulation not yet evaluated"
        missing_markers = ["Glucose", "glucose"]

    rows = confidence_increasers(facts={}, unknowns=[], hypotheses=[_Hypo(), _Hypo()])
    labels = [item["label"].lower() for item in rows]
    assert labels.count("assess glucose") <= 1


def test_b12_last_year_and_answers_now_do_not_reask(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    prior = {}
    control = None
    last = None
    for text in (
        "For six months both of my feet have burned at night.",
        "My last B12 check was last year.",
        "I want answers now. Is there any other insight?",
    ):
        last = orchestrate(text, prior_facts=prior, asked=[], answered=set(), control_state=control)
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        control = last.control
    extras = last.action.extras or {}
    assert extras.get("response_mode") in {"INTERIM_SYNTHESIS", "NEXT_STEPS"}
    assert extras.get("locked_verbalization") is True
    assert last.action.type != "ask_question"
    blob = (last.message + " " + (last.action.prompt or "")).lower()
    assert "last year" in blob
    assert "does not itself assess small-fiber" in blob or "does not itself assess small-fiber function" in blob
    assert "b12" in blob
    assert blob.count("check was last year") <= 1
    assert extras.get("explanation")
    assert extras.get("family_ids")
    view = extras["explanation"]
    assert view["families"]
    assert extras["family_ids"] == [item["id"] for item in view["families"]]
    assert extras["candidate_ids"] == [item.get("id") for item in view["ranked_actions"]]


def test_explanation_view_ids_match_panel_and_distinguish_coverage():
    class _Hypo:
        code = "small_fiber_dysfunction"
        label = "Small-fiber / peripheral sensory dysfunction"
        missing_markers = ["distribution"]
        not_a_diagnosis = "Not a diagnosis."

    view = build_explanation_view(hypotheses=[_Hypo()], facts={"laterality": "bilateral"})
    ids = {item["id"] for item in view["families"][0]["evaluations"]}
    assert "bf-emg" in ids
    assert "bf-exam" in ids
    assert "bf-b12" in ids
    emg = next(item for item in view["families"][0]["evaluations"] if item["id"] == "bf-emg")
    b12 = next(item for item in view["families"][0]["evaluations"] if item["id"] == "bf-b12")
    assert emg["coverage_relation"] == "does_not_address"
    assert b12["coverage_relation"] == "evaluates_contributor"
