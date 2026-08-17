from agent_protocol.digest import UatDigestEntry, render_digest, validate_entry
from agent_protocol.risk import (
    TIER_AUTONOMOUS,
    TIER_BLOCKED,
    TIER_FOUNDER,
    TIER_GUARDED,
    ChangeDescriptor,
    classify,
    load_policy,
)

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _base(**overrides) -> ChangeDescriptor:
    data = dict(
        target_environment="uat",
        deployment_action="uat_deploy",
        data_operation="none",
        contract_compatible=True,
        security_privacy_safety_effect="none",
        reasoning_integrity_effect="none",
        autonomous_permission_effect="none",
        medical_posture_effect="none",
        rollback_documented=True,
        tests_present=True,
        phi_introduced=False,
        reversible=True,
        change_class="ui",
        adr_present=False,
        feature_flagged=False,
        routine_blocker=None,
    )
    data.update(overrides)
    return ChangeDescriptor(**data)


def test_policy_file_loads_expected_tiers():
    policy = load_policy()
    assert set(policy["tiers"]) >= {TIER_AUTONOMOUS, TIER_GUARDED, TIER_FOUNDER, TIER_BLOCKED}
    assert "promote_or_deploy_main_production" in policy["founder_gates"]


def test_reversible_ui_is_autonomous_uat():
    decision = classify(_base())
    assert decision.tier == TIER_AUTONOMOUS
    assert decision.founder_interrupt is False
    assert decision.label == "uat-ready"


def test_additive_schema_with_evidence_is_guarded():
    decision = classify(
        _base(change_class="schema_additive", adr_present=True, tests_present=True, rollback_documented=True)
    )
    assert decision.tier == TIER_GUARDED
    assert decision.founder_interrupt is False


def test_production_promotion_is_founder_gate():
    assert classify(_base(target_environment="main", deployment_action="promote_main")).tier == TIER_FOUNDER
    assert classify(_base(deployment_action="production_deploy")).tier == TIER_FOUNDER


def test_one_way_doors_are_founder_gate():
    cases = [
        _base(data_operation="destructive_production"),
        _base(security_privacy_safety_effect="weaken"),
        _base(reasoning_integrity_effect="change"),
        _base(autonomous_permission_effect="expand"),
        _base(medical_posture_effect="diagnosis_claim"),
        _base(contract_compatible=False),
    ]
    for descriptor in cases:
        decision = classify(descriptor)
        assert decision.tier == TIER_FOUNDER, decision


def test_routine_failures_are_agent_blocked_not_founder():
    for blocker in ("ci_failure", "merge_conflict", "exhausted_correction_cycles", "uat_deploy_failure"):
        decision = classify(_base(routine_blocker=blocker))
        assert decision.tier == TIER_BLOCKED
        assert decision.founder_interrupt is False
        assert decision.label == "agent-blocked"


def test_malformed_or_missing_fields_fail_closed():
    assert classify(None).tier == TIER_FOUNDER
    assert classify(_base(target_environment=None)).tier == TIER_FOUNDER
    assert classify(_base(rollback_documented=None)).reason.startswith("missing_fields")


def test_digest_requires_traceability_fields():
    bad = UatDigestEntry(
        issue="",
        pr="#12",
        sha="short",
        risk_tier="autonomous-uat",
        rollback="revert sha",
        tests="pytest",
        uat_url="https://herbagraph-uat.up.railway.app/demo",
        deployment_state="SUCCESS",
        status="uat-ready",
    )
    assert "issue" in validate_entry(bad)
    assert "sha_not_full" in validate_entry(bad)
    good = UatDigestEntry(
        issue="#11",
        pr="#13",
        sha=SHA,
        risk_tier="autonomous-uat",
        rollback="revert to previous integration/agent SHA",
        tests="pytest tests/test_agent_protocol",
        uat_url="https://herbagraph-uat.up.railway.app/demo",
        deployment_state="SUCCESS",
        status="uat-ready",
    )
    text = render_digest([good])
    assert SHA in text and "autonomous-uat" in text
