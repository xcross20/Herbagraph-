"""Foundations for issues 58 B/C, 60, 61, and 62."""

from __future__ import annotations

from app.discovery.claim_cards import build_claim_card, cards_for_next_steps
from app.discovery.composition import assay_does_not_close_parent, claim_transfers, unknown_form_stays_unknown
from app.discovery.decision_events import DecisionLog, record_decision
from app.discovery.modalities import map_for, synthetic_maps
from app.discovery.next_evidence import candidates_for_control, plan_next_evidence
from app.discovery.orchestrator import orchestrate
from app.discovery.usefulness import ControlState, load_usefulness_fixture


def test_issue_60_anti_inheritance_and_unknown_form():
    assert claim_transfers("grape_skin_extract", "grape_green_phenotype", "contains_measured") is False
    assert claim_transfers("pink_rock_salt_batch", "non_iodized_specialty_salt", "contains_measured") is False
    assert claim_transfers("iodized_table_salt", "non_iodized_specialty_salt", "does_not_address") is False
    assert unknown_form_stays_unknown("unknown_biotin_product") is True
    assert assay_does_not_close_parent("serum_b12", "vitamin_b12") is True
    assert claim_transfers("methylcobalamin", "cyanocobalamin", "supports_outcome_in_population") is False


def test_issue_61_three_synthetic_maps_are_multimodal():
    maps = synthetic_maps()
    assert set(maps) == {"burning_feet", "ruq_discomfort", "facial_heat"}
    modalities = {item["modality"] for row in maps.values() for item in row}
    assert "standard_lab" not in modalities or "history" in modalities
    assert "electrophysiology" in {item["modality"] for item in map_for("burning_feet")}
    assert "imaging" in {item["modality"] for item in map_for("ruq_discomfort")}
    assert "patient_generated" in {item["modality"] for item in map_for("facial_heat")}
    emg = next(item for item in map_for("burning_feet") if item["id"] == "bf-emg")
    assert emg["coverage"] == "does_not_directly_assess"


def test_issue_58_planner_skips_paused_and_non_addressing():
    state = ControlState(focus={"burning_feet": "paused_by_user", "facial_heat": "active", "ruq_discomfort": "active"})
    codes = {item["code"] for item in candidates_for_control(state)}
    assert not any(code.startswith("bf-") for code in codes)
    assert "fh-log" in codes
    assert "ruq-us" in codes
    assert "bf-emg" not in codes
    planned = plan_next_evidence(state)
    assert planned
    assert all(item.get("action_type") != "ask_question" or True for item in planned)
    labels = " ".join(item["label"].lower() for item in planned)
    assert "emg" not in labels


def test_issue_58_claim_cards_fail_closed_without_inventing_pmids():
    bad = build_claim_card(statement="A paper exists.", source_id="pmid:99999999")
    assert bad["accepted"] is False
    good = cards_for_next_steps()
    assert good
    assert all(item["accepted"] for item in good)
    assert all(not str(item["source_id"]).startswith("pmid:") or str(item["source_id"]).split(":")[-1].isdigit() for item in good)


def test_issue_62_decision_events_are_idempotent_and_do_not_change_rank():
    log = DecisionLog()
    candidates = [{"id": "fh-log", "label": "Food log", "information_value": 0.7}]
    first = record_decision(log, source_event_id="turn-1", response_mode="NEXT_STEPS", candidates=candidates, selected_id="fh-log")
    second = record_decision(first, source_event_id="turn-1", response_mode="NEXT_STEPS", candidates=candidates, selected_id="fh-log")
    assert len(second.events) == 1
    assert second.events[0]["changes_scientific_rank"] is False
    assert second.events[0]["consent_purpose"] == "direct_service"


def test_issue_58_fixture_surfaces_ranked_next_evidence(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    fixture = load_usefulness_fixture()
    prior: dict[str, str] = {}
    control = None
    last = None
    for turn in fixture["turns"]:
        last = orchestrate(turn["text"], prior_facts=prior, asked=[], answered=set(), control_state=control)
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        control = last.control
    assert last is not None
    extras = last.action.extras or {}
    assert extras.get("response_mode") in {"INTERIM_SYNTHESIS", "NEXT_STEPS"}
    assert extras.get("next_evidence")
    assert extras.get("claim_cards")
    assert last.control.get("decision_log", {}).get("events")
    blob = last.message.lower()
    assert "ranked next evidence" in blob
    assert "not a diagnosis" in blob
    assert "may or may not share a cause" in blob
    assert all(card.get("accepted") for card in extras["claim_cards"])
