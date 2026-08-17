"""PR-B coverage/evidence contract.

Unit mapping, resolver hostility, persist-path attach, and map buckets.
ISS-08 (branch close) stays scaffolded until PR-E.
"""

from __future__ import annotations

from app.discovery.coverage_governor import assess_coverage
from app.discovery.engine import rebuild_case_state
from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.evidence_mapping import coverage_to_evidence_relationship
from app.discovery.epistemics import coverage_to_evidence_relationship as epistemic_mapper
from app.discovery.map import build_map_payload
from app.discovery.resolver import resolve_test
from app.models.enums import CoverageRelation, EvidenceRelationship, ResolverStatus



def test_not_applicable_creates_no_evidence_relationship():
    assert coverage_to_evidence_relationship("not_applicable") is None
    assert epistemic_mapper("not_applicable") is None


def test_unknown_coverage_creates_no_evidence_relationship():
    assert coverage_to_evidence_relationship("unknown") is None


def test_does_not_directly_assess_maps_to_does_not_address():
    mapped = coverage_to_evidence_relationship("does_not_directly_assess")
    value = mapped.value if hasattr(mapped, "value") else mapped
    assert value == "does_not_address"


def test_directly_assesses_without_branch_rule_creates_no_generic_edge():
    assert coverage_to_evidence_relationship("directly_assesses") is None


def test_resolver_exact_and_alias_emg():
    exact = resolve_test("EMG / nerve conduction study")
    alias = resolve_test("emg")
    assert exact.status is ResolverStatus.MATCHED
    assert exact.match is not None and exact.match.code == "emg_ncs"
    assert alias.status is ResolverStatus.MATCHED
    assert alias.match is not None and alias.match.code == "emg_ncs"


def test_resolver_generic_mri_is_ambiguous_not_brain():
    result = resolve_test("MRI")
    assert result.status is ResolverStatus.AMBIGUOUS
    assert result.match is None
    codes = {item.code for item in result.candidates}
    assert "mri_brain" in codes
    assert len(codes) > 1


def test_resolver_unknown_and_hostile_unicode_unresolved():
    assert resolve_test("quantum aura scan").status is ResolverStatus.UNRESOLVED
    assert resolve_test("EMG\u200b").status is ResolverStatus.MATCHED
    assert resolve_test("").status is ResolverStatus.UNRESOLVED


def test_unrelated_emg_must_not_attach_to_biliary_persist_path():
    """ISS-02 persist path: gallbladder + EMG creates no biliary edge."""
    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["biliary_stones", "small_fiber_density"],
        result_state="negative",
    )
    biliary = [edge for edge in interpreted.edges if edge.branch_code == "biliary_stones"]
    small_fiber = [edge for edge in interpreted.edges if edge.branch_code == "small_fiber_density"]
    assert biliary == []
    assert len(small_fiber) == 1
    assert small_fiber[0].relationship is EvidenceRelationship.DOES_NOT_ADDRESS
    assert small_fiber[0].coverage is CoverageRelation.DOES_NOT_DIRECTLY_ASSESS
    assert assess_coverage("emg_ncs", "biliary_stones").relation is CoverageRelation.NOT_APPLICABLE


def test_map_payload_represents_non_addressing_and_unresolved():
    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    payload = build_map_payload(
        snapshot=snapshot,
        facts={"burning sensation": "reported"},
        unknowns=[],
        evidence_by_branch={
            getattr(snapshot.hypotheses[0], "code", ""): {
                "does_not_address": ["EMG/NCS does not measure small-fiber density."],
                "unresolved": ["MRI"],
            }
        },
    )
    assert payload["not_disease_probability"] is True
    found = False
    for branch in payload["branches"]:
        assert "does_not_address" in branch
        assert "unresolved" in branch
        assert "supports" in branch
        if branch["does_not_address"]:
            found = True
    assert found


def test_non_addressing_evidence_cannot_close_branch():
    """ISS-08: EMG that does not directly assess small-fiber cannot set closed/resolved_at."""
    from app.discovery.lifecycle import propose_transition
    from app.models.enums import BranchLifecycleStatus

    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["small_fiber_density"],
        result_state="negative",
    )
    edge = interpreted.edges[0]
    decision = propose_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=edge.coverage,
        relationship=edge.relationship,
    )
    assert decision.accepted is False
    assert decision.resolved_at is None
    assert decision.status is BranchLifecycleStatus.NOT_EVALUATED
