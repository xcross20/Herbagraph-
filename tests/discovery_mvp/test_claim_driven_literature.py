"""Issue 58 UAT: ontology example seeds cannot become Case literature."""

from __future__ import annotations

from app.discovery.claim_cards import cards_for_next_steps, is_seed_literature
from app.discovery.explanation import build_explanation_view, render_explanation_text
from app.discovery.orchestrator import orchestrate
from app.discovery.telemetry import reset, snapshot


def test_ruq_case_does_not_render_grape_or_salt_seeds():
    reset()
    class _Hypo:
        code = "biliary_colic_pattern"
        label = "Biliary-type episodic pain pattern"
        missing_markers = []
        not_a_diagnosis = "Not a diagnosis."

    view = build_explanation_view(
        hypotheses=[_Hypo()],
        facts={"location": "ruq", "meal_relation": "after_fatty_meal"},
    )
    titles = " ".join(str(item.get("title") or "") for item in view["claim_cards"]).lower()
    assert "grape" not in titles
    assert "pink-salt" not in titles
    assert "pink salt" not in titles
    cards = cards_for_next_steps(["biliary_colic_pattern"], facts={"location": "ruq"}, text="pain after burgers and fries")
    assert cards == []
    counts = snapshot()
    assert any(key.startswith("citation_rejected_") for key in counts)


def test_burgers_and_fries_do_not_unlock_grape_papers():
    cards = cards_for_next_steps(
        ["biliary_colic_pattern", "food_composition"],
        facts={"fatty_food": "burgers and fries"},
        text="It happens after burgers and fries",
    )
    assert cards == []


def test_grape_exposure_without_selected_claim_still_fails_closed():
    cards = cards_for_next_steps(
        ["biliary_colic_pattern"],
        facts={"grape_exposure": "reported"},
        text="I also eat grapes",
    )
    assert cards == []
    still_seed = cards_for_next_steps(
        ["grape"],
        facts={"grape_exposure": "reported"},
        active_claim_ids=["claim-grape-composition", "grape"],
        text="Does grape color change the dose?",
    )
    assert still_seed == []


def test_title_similarity_without_entailment_is_not_enough():
    assert is_seed_literature({"title": "Grape bioactive composition review", "source_id": "pmc:8567006"})
    leaked = cards_for_next_steps(["small_fiber_dysfunction"], facts={}, text="bioactive composition review")
    assert leaked == []


def test_ruq_answers_now_uses_panel_plan_not_seed_papers(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    prior = {}
    control = None
    last = None
    for text in (
        "There is some mild discomfort under my right ribs after fatty meals.",
        "It starts an hour or more after eating.",
        "What do you think I should do?",
    ):
        last = orchestrate(text, prior_facts=prior, asked=[], answered=set(), control_state=control)
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        control = last.control
    extras = last.action.extras or {}
    assert extras.get("response_mode") in {"INTERIM_SYNTHESIS", "NEXT_STEPS"}
    blob = (last.message + " " + (last.action.prompt or "")).lower()
    assert "grape" not in blob
    assert "pink-salt" not in blob
    assert "ultrasound" in blob or extras.get("candidate_ids")
    assert "right-upper" in blob or "right upper" in blob or "rib" in blob
    cards = extras.get("claim_cards") or []
    assert not any(is_seed_literature(item) for item in cards)
    view = extras.get("explanation") or {}
    text = render_explanation_text(view, facts=prior)
    assert "small-fiber" not in text.lower()
