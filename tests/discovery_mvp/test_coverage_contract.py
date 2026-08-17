"""DI-13, DI-14, ADR-MVP-002. Mapping seam must exist and must not guess."""

import pytest

from app.discovery.map import build_map_payload
from app.discovery.engine import rebuild_case_state


def _mapping():
    try:
        from app.discovery.epistemics import coverage_to_evidence_relationship
    except ImportError:
        from app.discovery.evidence_mapping import coverage_to_evidence_relationship
    return coverage_to_evidence_relationship


def test_not_applicable_creates_no_evidence_relationship():
    mapped = _mapping()("not_applicable")
    assert mapped is None


def test_unknown_coverage_creates_no_evidence_relationship():
    mapped = _mapping()("unknown")
    assert mapped is None


def test_does_not_directly_assess_maps_to_does_not_address():
    mapped = _mapping()("does_not_directly_assess")
    value = mapped.value if hasattr(mapped, "value") else mapped
    assert value == "does_not_address"


def test_map_payload_must_not_carry_diagnostic_certainty():
    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    payload = build_map_payload(snapshot=snapshot, facts={"burning sensation": "reported"}, unknowns=[])
    blob = str(payload).lower()
    assert "certainty" not in blob
    assert "disease_probability" not in blob
    for branch in payload.get("branches") or []:
        assert "certainty" not in branch
