"""Scientific Governance / Scientific Output Engine adapter.

Wraps: app.discovery.scientific_output
Contract: docs/personal-evidence/REASONING_CORE_ARCHITECTURE.md §3.6

The Scientific Governor is a synchronous validation layer that runs before any
output is verbalized or stored. It governs:
  - Language: no disease claims, no causal language without sufficient evidence
  - Coverage: test limitations are stated, not omitted
  - Evidence: applicability limits are attached, not stripped
  - Safety: safety_status in TurnResult governs triage level (S0–S4)

Anti-patterns this governor enforces:
  - "This confirms neuropathy."         → REJECTED
  - "Your normal EMG rules out..."   → REJECTED
  - "This test was normal, therefore → REJECTED
    this branch is resolved."
  - "Magnesium glycinate is          → REJECTED
    equivalent to magnesium oxide."
  - "500mg magnesium glycinate        → REJECTED
    means 500mg elemental magnesium."

Governed by: app.discovery.scientific_output.validate_scientific_output
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Delegation ──────────────────────────────────────────────────────────────

from app.discovery.scientific_output import (  # noqa: E402
    ScientificItem,
    ScientificItemType,
    validate_scientific_output as _validate,
    ValidationResult,
)


# ── Typed result ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScientificGovernanceResult:
    """Outcome of scientific-output governance validation."""

    valid: bool
    """False when the output violates scientific-output policy."""

    violations: tuple[str, ...]
    """Human-readable violation codes when valid is False."""

    safe_replacement: str | None
    """The safe fallback text when the output was rejected."""


# ── Public API ──────────────────────────────────────────────────────────────


def validate_scientific_output(
    items: list[ScientificItem],
    *,
    commerce_boosted: bool = False,
    stored_pmids: set[str] | None = None,
) -> ScientificGovernanceResult:
    """
    Validate a list of ScientificItem statements for scientific-output policy compliance.

    The function is synchronous and deterministic — no LLM dependency.

    Violations that cause rejection:
      - diagnostic language: "you have", "this confirms", "diagnosis is", etc.
      - unsupported causal language: "this caused", "proves that", etc.
      - coverage misuse: "rules out", "ruled out", "negative evidence that you do not"
      - sourceless inference (non-GAP items without provenance)
      - commerce-boosted ranking
      - unknown coverage as negative evidence
      - malformed or unresolved citation IDs

    Returns ScientificGovernanceResult:
      - valid: False when any violation is detected
      - violations: tuple of violation codes
      - safe_replacement: safe fallback text or None
    """
    result: ValidationResult = _validate(
        items,
        commerce_boosted=commerce_boosted,
        stored_pmids=stored_pmids,
    )
    return ScientificGovernanceResult(
        valid=result.accepted,
        violations=tuple(result.violations),
        safe_replacement=result.replacement,
    )


# Re-export types for consumers
__all__ = ["ScientificItem", "ScientificItemType", "ScientificGovernanceResult", "validate_scientific_output"]
