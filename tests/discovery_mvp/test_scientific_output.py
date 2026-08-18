"""SO-02 public surfaces must not expose diagnostic certainty.

Inspect explicit keys. Do not substring-search the payload: the map
intentionally contains `not_disease_probability`, which contains
`disease_probability` as a substring.

Compatibility: ADR-MVP-001. PR-A does not remove the fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.discovery.engine import rebuild_case_state
from app.discovery.map import build_map_payload
from app.discovery.service import snapshot_to_read
from app.models.discovery import DiscoveryCase
from app.models.enums import DiscoveryCaseStatus
from app.schemas.discovery import DiscoveryHypothesisRead
REPO_ROOT = Path(__file__).resolve().parents[2]
CERTAINTY_KEYS = frozenset(
    {
        "certainty",
        "diagnostic_certainty",
        "diagnostic_certainty_percent",
    }
)


def _assert_no_certainty_keys(node) -> None:
    if isinstance(node, dict):
        present = CERTAINTY_KEYS.intersection(node)
        assert not present, f"forbidden certainty keys present: {sorted(present)}"
        for value in node.values():
            _assert_no_certainty_keys(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_certainty_keys(item)


def test_map_scientific_output_gate_strips_diagnostic_notes():
    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    payload = build_map_payload(snapshot=snapshot, facts={"burning sensation": "reported"}, unknowns=[])
    payload["coverage_notes"] = ["You have small-fiber neuropathy.", "Small-fiber investigation remains open."]
    from app.discovery.map import _apply_scientific_output_gate

    gated = _apply_scientific_output_gate(payload)
    assert gated["scientific_output_accepted"] is True
    assert "scientific_output_violations" not in gated
    assert "You have small-fiber neuropathy." not in gated["coverage_notes"]
    assert "Small-fiber investigation remains open." in gated["coverage_notes"]


def test_map_payload_must_not_carry_diagnostic_certainty_keys():
    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    payload = build_map_payload(snapshot=snapshot, facts={"burning sensation": "reported"}, unknowns=[])
    assert payload.get("not_disease_probability") is True
    _assert_no_certainty_keys(payload)
    for branch in payload.get("branches") or []:
        assert "certainty" not in branch
        assert "diagnostic_certainty" not in branch
        assert "diagnostic_certainty_percent" not in branch


def test_api_serializer_must_not_expose_diagnostic_certainty_fields():
    schema_fields = set(DiscoveryHypothesisRead.model_fields)
    assert "diagnostic_certainty" not in schema_fields
    assert "diagnostic_certainty_percent" not in schema_fields

    snapshot = rebuild_case_state("For six months my feet have burned at night.", [], {})
    now = datetime.now(timezone.utc)
    case = DiscoveryCase(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        presenting_concern=snapshot.presenting_concern,
        status=DiscoveryCaseStatus.OPEN,
        created_at=now,
        updated_at=now,
    )
    dumped = snapshot_to_read(case, snapshot).model_dump()
    _assert_no_certainty_keys(dumped)
    for hypothesis in dumped.get("hypotheses") or []:
        assert "diagnostic_certainty" not in hypothesis
        assert "diagnostic_certainty_percent" not in hypothesis


def test_frontend_must_not_render_diagnostic_certainty():
    workspace = (REPO_ROOT / "frontend" / "js" / "workspace-app.js").read_text(encoding="utf-8")
    assert "Diagnostic certainty" not in workspace
    assert "diagnostic_certainty_percent" not in workspace
