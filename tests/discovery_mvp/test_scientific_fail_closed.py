"""PR-50: invalid scientific output never reaches the user."""

from __future__ import annotations

from app.discovery.map import _apply_scientific_output_gate
from app.discovery.scientific_output import (
    SAFE_LIMITATION,
    ScientificItem,
    fail_closed_text,
    validate_scientific_output,
    verify_citations,
)
from app.models.enums import ScientificItemType


def _item(statement: str, **kwargs) -> ScientificItem:
    payload = {
        "id": kwargs.pop("id", "x"),
        "version": "1",
        "item_type": ScientificItemType.SYSTEM_INFERENCE,
        "statement": statement,
        "provenance": kwargs.pop("provenance", ["coverage-catalog-v1"]),
    }
    payload.update(kwargs)
    return ScientificItem(**payload)


def test_diagnostic_and_probability_language_fail_closed():
    for statement in (
        "You have small-fiber neuropathy.",
        "This confirms the diagnosis.",
        "There is an 80% chance this is neuropathy.",
        "The likelihood of disease is high.",
    ):
        result = validate_scientific_output([_item(statement)])
        assert result.accepted is False
        assert result.replacement == SAFE_LIMITATION
        assert fail_closed_text(statement) == SAFE_LIMITATION


def test_fabricated_and_malformed_citations_fail_closed():
    assert verify_citations(["99999999"], {"12345678"}) == ["citation_unresolved:99999999"]
    assert verify_citations(["not-a-pmid"], {"12345678"}) == ["citation_malformed:not-a-pmid"]
    assert verify_citations(["12345678", "12345678"], {"12345678"}) == ["citation_duplicate:12345678"]
    result = validate_scientific_output(
        [_item("A paper is cited.", citations=["99999999"])],
        stored_pmids={"12345678"},
    )
    assert result.accepted is False
    assert any("citation_unresolved" in item for item in result.violations)


def test_unknown_coverage_cannot_be_negative_evidence():
    result = validate_scientific_output(
        [_item("EMG rules out gallbladder disease.")],
        unknown_as_negative=True,
    )
    assert result.accepted is False
    assert "unknown_coverage_as_negative" in result.violations
    assert any("coverage_misuse" in item for item in result.violations)


def test_temporal_monitoring_cannot_become_causal_claim():
    result = validate_scientific_output(
        [_item("This caused your burning to improve because you took B12.")]
    )
    assert result.accepted is False
    assert any("unsupported_causal_language" in item for item in result.violations)


def test_commerce_boost_and_strength_collapse_fail_closed():
    result = validate_scientific_output(
        [
            _item(
                "An option remains open.",
                evidence_strength="high",
                case_confidence="high",
            )
        ],
        commerce_boosted=True,
    )
    assert result.accepted is False
    assert "commerce_cannot_change_scientific_rank" in result.violations
    assert any("strength_collapsed" in item for item in result.violations)


def test_invalid_map_notes_never_render():
    gated = _apply_scientific_output_gate(
        {
            "coverage_notes": ["You have neuropathy.", "Small-fiber density remains open."],
            "disclaimer": "This confirms a diagnosis.",
            "provenance": ["coverage-catalog-v1"],
        }
    )
    assert "You have neuropathy." not in gated["coverage_notes"]
    assert gated["disclaimer"] == "This is not a diagnosis."
    assert "scientific_output_violations" not in gated
    assert gated["scientific_output_accepted"] is True


def test_resolved_citation_is_allowed():
    result = validate_scientific_output(
        [_item("A stored paper is cited.", citations=["12345678"])],
        stored_pmids={"12345678"},
    )
    assert result.accepted is True
    assert result.replacement is None
