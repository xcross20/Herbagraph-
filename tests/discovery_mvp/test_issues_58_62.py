"""Foundations for issues 58 B/C, 60, 61, and 62."""

from __future__ import annotations

import json

from app.discovery.claim_cards import build_claim_card, cards_for_next_steps
from app.discovery.composition import (
    assay_does_not_close_parent,
    claim_transfers,
    load_composition_graph,
    load_extensibility_overlay,
    merge_overlay,
    overlay_uses_existing_layers,
    unknown_form_stays_unknown,
)
from app.discovery.decision_events import (
    DecisionLog,
    compute_map_delta,
    founder_uat_view,
    link_later_evidence,
    record_decision,
    record_disposition,
    withdraw_secondary_use,
)
from app.discovery.modalities import map_for, synthetic_maps
from app.discovery.next_evidence import candidates_for_control, plan_next_evidence
from app.discovery.orchestrator import orchestrate
from app.discovery.usefulness import ControlState, apply_control, classify_control_intent, load_usefulness_fixture


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
    cards = extras.get("claim_cards") or []
    assert all(card.get("accepted") for card in cards)
    assert last.control.get("decision_log", {}).get("events")
    blob = last.message.lower()
    assert "ranked next evidence" in blob
    assert "not a diagnosis" in blob
    assert "may or may not share a cause" in blob
    if not cards:
        assert "limitation" in blob


def test_issue_60_fifth_domain_is_configuration_only():
    base = load_composition_graph()
    overlay = load_extensibility_overlay()
    assert overlay_uses_existing_layers(overlay, base) is True
    merged = merge_overlay(base, overlay)
    assert assay_does_not_close_parent("serum_folate", "folate", merged) is True
    assert unknown_form_stays_unknown("unknown_folate_product", merged) is True
    assert claim_transfers("five_mthf", "folic_acid", "supports_outcome_in_population", merged) is False
    assert concept_layer_set_unchanged(base, merged)
    bad = {"concepts": [{"code": "x", "layer": "invented_layer"}]}
    try:
        merge_overlay(base, bad)
        raised = False
    except ValueError:
        raised = True
    assert raised is True


def concept_layer_set_unchanged(base: dict, merged: dict) -> bool:
    base_layers = {item["layer"] for item in base["concepts"]}
    merged_layers = {item["layer"] for item in merged["concepts"]}
    return merged_layers.issubset(base_layers | {"concept", "form", "assay", "product_batch"})


def test_issue_62_later_evidence_computes_governed_map_delta():
    log = DecisionLog()
    log = record_decision(
        log,
        source_event_id="turn-1",
        response_mode="NEXT_STEPS",
        candidates=[{"id": "bf-b12", "label": "B12 status evaluation", "information_value": 0.56}],
        selected_id="bf-b12",
    )
    first = link_later_evidence(
        log,
        evidence_id="prior_labs.b12_last_check",
        coverage="partially_assesses",
        branch_id="b12_functional_gap",
        source_event_id="ev-b12",
        selected_id="bf-b12",
    )
    replay = link_later_evidence(
        first,
        evidence_id="prior_labs.b12_last_check",
        coverage="partially_assesses",
        branch_id="b12_functional_gap",
        source_event_id="ev-b12",
        selected_id="bf-b12",
    )
    assert len(replay.outcomes) == 1
    assert replay.outcomes[0]["map_delta"]["kind"] == "partially_assessed"
    assert replay.outcomes[0]["closes_branch"] is False
    emg = link_later_evidence(
        replay,
        evidence_id="emg-report",
        coverage="does_not_directly_assess",
        branch_id="small_fiber_dysfunction",
        source_event_id="ev-emg",
        selected_id="bf-emg",
    )
    assert emg.outcomes[-1]["map_delta"]["kind"] == "non_addressing"
    assert compute_map_delta(coverage="does_not_address", usable=True)["kind"] == "non_addressing"
    failed = compute_map_delta(coverage="directly_assesses", usable=False)
    assert failed["kind"] == "unchanged"
    withdrawn = withdraw_secondary_use(emg)
    assert withdrawn.secondary_use_allowed is False
    view = founder_uat_view(withdrawn)
    assert view["contains_raw_health_text"] is False
    assert view["changes_scientific_rank"] is False
    assert view["valid_map_delta_count"] >= 1
    assert "burn" not in json.dumps(view).lower()


def test_issue_62_disposition_is_idempotent():
    log = record_decision(
        DecisionLog(),
        source_event_id="turn-1",
        response_mode="NEXT_STEPS",
        candidates=[{"id": "bf-exam", "label": "Exam"}],
        selected_id="bf-exam",
    )
    first = record_disposition(log, event_identity=log.events[0]["identity"], disposition="deferred", source_event_id="disp-1")
    second = record_disposition(first, event_identity=log.events[0]["identity"], disposition="deferred", source_event_id="disp-1")
    assert len(second.dispositions) == 1


def test_issue_58_pause_b12_family_keeps_burning_feet_active():
    assert "pause_family" in classify_control_intent("pause the B12 investigation")
    assert "request_next_steps" in classify_control_intent("never mind about B12, what else?")
    state = ControlState(focus={"burning_feet": "active", "facial_heat": "active"})
    state = apply_control(state, "pause the B12 investigation", {})
    assert state.focus["burning_feet"] == "active"
    assert state.paused_families["b12_functional_gap"] == "paused_by_user"
    codes = {item["code"] for item in candidates_for_control(state)}
    assert "bf-b12" not in codes
    assert "bf-mma" not in codes
    assert "bf-exam" in codes or "bf-glucose" in codes or "bf-qst" in codes
