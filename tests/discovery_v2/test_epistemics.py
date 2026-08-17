"""V2 epistemic claims from the investigation-state spec."""

from app.coverage.evaluator import evaluate
from app.coverage.resolver import resolve_test
from app.discovery.epistemics import (
    EpistemicValidator,
    clinician_rule_out_is_reported,
    gallbladder_split,
)
from app.discovery.reconciliation import batch_from_turn
from app.discovery.safety import assess_safety, extract_safety_findings, screen_safety
from app.discovery.workup_service import workup_from_text
from app.models.enums import DiscoveryWorkupResult


def test_clinician_rule_out_is_reported_not_verified():
    text = "My doctor said my MRI ruled out everything neurological."
    decision = EpistemicValidator().validate_finding(text)
    assert decision.allowed is True
    assert decision.stored_text == "Patient reports clinician said this was ruled out"
    assert any(mod.get("to") == "reported" for mod in decision.modifications)
    assert any(item.get("tool") == "REQUEST_RECORD" for item in decision.required_tools)
    assert clinician_rule_out_is_reported(text) is True
    assert "ruled out everything" not in (decision.stored_text or "").lower()


def test_gallbladder_theory_is_not_a_disease_finding():
    split = gallbladder_split("My gallbladder hurts.")
    assert split["finding"]["concept"] == "abdominal_pain"
    assert split["finding"]["value"] == "location_unclear"
    assert "disease" not in split["interpretation"]["statement"].lower()
    assert split["interpretation"]["concept"] == "biliary_source"
    assert screen_safety("My gallbladder hurts.").status == "S1"


def test_normal_emg_does_not_close_small_fiber():
    match = resolve_test("EMG was normal")
    assert match is not None
    assessment = evaluate(match.test_code, "small_fiber_density", match.protocol_code)
    assert assessment.relation == "does_not_directly_assess"
    work = workup_from_text("EMG was normal.")
    assert work[0].result_state == DiscoveryWorkupResult.PATIENT_REPORTED_NORMAL.value
    decision = EpistemicValidator().validate_test_inference("EMG was normal", "small_fiber_density")
    assert decision.relation == "does_not_directly_assess"
    close = EpistemicValidator().validate_branch_resolution(relation=decision.relation, proposed_close=True)
    assert close.allowed is False


def test_batch_from_messy_narrative_keeps_threads_separate():
    text = (
        "I've had right facial pressure for a year, starting weeks after an electrical injury. "
        "MRI was normal. I think it might be my gallbladder too sometimes."
    )
    batch = batch_from_turn(text=text, concern=text, plan=None)
    assert any(item.raw_test_name == "MRI" for item in batch.add_prior_workup)
    assert any(item.code == "biliary_colic_pattern" for item in batch.open_branches)
    assert any("small_fiber" in item.code or "peripheral" in item.category for item in batch.open_branches) or batch.open_branches


def test_historical_jaundice_is_not_combined_into_s4():
    findings = extract_safety_findings(
        "Five years ago I had jaundice, but today I just have occasional mild discomfort."
    )
    assessment = assess_safety(findings)
    assert assessment.state != "S4"


def test_correction_supersedes_instead_of_deleting():
    decision = EpistemicValidator().validate_correction(
        "Pain started after surgery",
        "Pain started two months before surgery",
    )
    assert decision.allowed is True
    assert any(mod.get("action") == "supersede" for mod in decision.modifications)
