"""PR-48: general coverage, evidence, lifecycle, and reproducible maps."""

from __future__ import annotations

import random

from app.discovery.coverage_catalog import CATALOG_PATH, catalog_version, explain_relation
from app.discovery.coverage_governor import assess_coverage
from app.discovery.coverage_validation import validate_coverage_catalog
from app.discovery.engine import rebuild_case_state
from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.lifecycle import LEGAL, apply_transition, propose_transition
from app.discovery.map import build_map_payload, payload_fingerprint
from app.models.enums import BranchLifecycleStatus, CoverageRelation, EvidenceRelationship


FORBIDDEN_GOLD_PHRASES = (
    "A normal EMG does not assess small-fiber density.",
    "Small-fiber investigation remains open.",
    "EMG is not evidence about biliary structure.",
)


def test_catalog_passes_authoring_validation():
    result = validate_coverage_catalog()
    assert result.accepted is True, result.errors
    assert result.version == catalog_version()


def test_catalog_rejects_duplicate_contradictory_and_unprovenanced_rules():
    from app.discovery.coverage_catalog import CatalogRelation, CoverageCatalog, load_catalog

    catalog = load_catalog()
    bad = CoverageCatalog(
        version=catalog.version,
        tests=catalog.tests,
        concepts=catalog.concepts,
        relations=catalog.relations
        + (
            CatalogRelation("emg_ncs", "small_fiber_density", "directly_assesses", "x", provenance=""),
            CatalogRelation("emg_ncs", "emg_ncs", "directly_assesses", "y", provenance="loop"),
        ),
        branch_concepts=catalog.branch_concepts,
        body_sites=catalog.body_sites,
        modalities=catalog.modalities,
        provenance=catalog.provenance,
    )
    result = validate_coverage_catalog(bad)
    assert result.accepted is False
    blob = " ".join(result.errors)
    assert "contradictory_rule" in blob
    assert "missing_provenance" in blob
    assert "circular_identity" in blob


def test_production_rules_do_not_store_gold_case_phrases():
    raw = CATALOG_PATH.read_text(encoding="utf-8")
    for phrase in FORBIDDEN_GOLD_PHRASES:
        assert phrase not in raw


def test_explanations_are_generated_from_relations():
    note = explain_relation(
        test_name="EMG / nerve conduction study",
        concept_label="small-fiber density",
        relation="does_not_directly_assess",
    )
    assert "does not directly assess" in note
    assert "small-fiber density" in note
    for phrase in FORBIDDEN_GOLD_PHRASES:
        assert phrase != note


def test_normal_emg_does_not_address_small_fiber_and_cannot_close():
    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["small_fiber_density"],
        result_state="negative",
    )
    assert len(interpreted.edges) == 1
    edge = interpreted.edges[0]
    assert edge.coverage is CoverageRelation.DOES_NOT_DIRECTLY_ASSESS
    assert edge.relationship is EvidenceRelationship.DOES_NOT_ADDRESS
    assert edge.rule_version == catalog_version()
    decision = propose_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=edge.coverage,
        relationship=edge.relationship,
    )
    assert decision.accepted is False
    assert decision.status is BranchLifecycleStatus.NOT_EVALUATED


def test_emg_versus_biliary_is_unknown_and_creates_no_edge():
    interpreted = interpret_workup(
        raw_label="EMG",
        branch_codes=["biliary_stones"],
        result_state="negative",
    )
    assert interpreted.edges == []
    assert assess_coverage("emg_ncs", "biliary_stones").relation is CoverageRelation.UNKNOWN


def test_direct_biopsy_can_change_small_fiber_coverage():
    interpreted = interpret_workup(
        raw_label="skin biopsy",
        branch_codes=["small_fiber_density"],
        result_state="positive",
    )
    assert len(interpreted.edges) == 1
    edge = interpreted.edges[0]
    assert edge.coverage is CoverageRelation.DIRECTLY_ASSESSES
    assert edge.relationship is EvidenceRelationship.SUPPORTS
    decision = propose_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=edge.coverage,
        relationship=edge.relationship,
    )
    assert decision.accepted is True
    assert decision.status is BranchLifecycleStatus.CLOSED


def test_unknown_test_never_resolves_by_guess():
    interpreted = interpret_workup(raw_label="quantum aura scan", branch_codes=["small_fiber_density"])
    assert interpreted.edges == []
    assert interpreted.unresolved == ["quantum aura scan"]
    assert assess_coverage("quantum_aura", "small_fiber_density").relation is CoverageRelation.UNKNOWN


def test_lifecycle_table_is_exhaustive():
    statuses = list(BranchLifecycleStatus)
    for current in statuses:
        assert current in LEGAL
        for proposed in statuses:
            decision = propose_transition(current, proposed)
            if proposed is current:
                assert decision.accepted is True
            elif proposed not in LEGAL[current]:
                assert decision.accepted is False
                assert decision.reason == "illegal_transition"


def test_reopen_preserves_prior_closure_event_and_reason():
    closed = apply_transition(
        BranchLifecycleStatus.NOT_EVALUATED,
        BranchLifecycleStatus.CLOSED,
        coverage=CoverageRelation.DIRECTLY_ASSESSES,
        relationship=EvidenceRelationship.SUPPORTS,
    )
    assert closed.accepted is True
    reopened = apply_transition(
        BranchLifecycleStatus.CLOSED,
        BranchLifecycleStatus.REOPENED,
        explicit_reopen=True,
        resolved_at=closed.resolved_at,
        close_reason=closed.close_reason,
    )
    assert reopened.accepted is True
    assert reopened.status is BranchLifecycleStatus.REOPENED
    assert reopened.prior_resolved_at == closed.resolved_at
    assert reopened.prior_close_reason == closed.close_reason
    assert reopened.resolved_at is None


def test_map_is_reproducible_and_order_independent():
    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    first = build_map_payload(
        snapshot=snapshot,
        facts={"emg testing": "reported_normal", "burning sensation": "reported"},
        unknowns=[],
    )
    second = build_map_payload(
        snapshot=snapshot,
        facts={"emg testing": "reported_normal", "burning sensation": "reported"},
        unknowns=[],
    )
    assert payload_fingerprint(first) == payload_fingerprint(second)
    assert first["coverage"]["emg_ncs"]["small_fiber_density"] == "does_not_directly_assess"
    assert catalog_version() in first["provenance"]
    for phrase in FORBIDDEN_GOLD_PHRASES:
        assert phrase not in " ".join(first["coverage_notes"])

    keys = list(first["coverage"].keys())
    random.shuffle(keys)
    shuffled = {key: first["coverage"][key] for key in keys}
    assert shuffled == first["coverage"]


def test_rule_version_change_changes_fingerprint(monkeypatch):
    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    baseline = build_map_payload(
        snapshot=snapshot,
        facts={"emg testing": "reported_normal"},
        unknowns=[],
    )

    def _other_version() -> str:
        return "coverage-catalog-v2-test"

    monkeypatch.setattr("app.discovery.coverage_catalog.catalog_version", _other_version)
    changed = build_map_payload(
        snapshot=snapshot,
        facts={"emg testing": "reported_normal"},
        unknowns=[],
    )
    assert payload_fingerprint(baseline) != payload_fingerprint(changed)
