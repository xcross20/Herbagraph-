"""Scientific-output contract and validator (Milestone 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import ScientificItemType

FORBIDDEN_DIAGNOSTIC = ("you have", "this confirms", "this proves", "diagnosis is", "disease probability")


@dataclass
class ScientificItem:
    id: str
    version: str
    item_type: ScientificItemType
    statement: str
    provenance: list[str]
    evidence_strength: str | None = None
    case_confidence: str | None = None
    supports: list[str] = field(default_factory=list)
    weakens: list[str] = field(default_factory=list)
    does_not_address: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    safety_constraints: list[str] = field(default_factory=list)
    rationale: str = ""
    last_evaluated_at: str | None = None


@dataclass
class ValidationResult:
    accepted: bool
    violations: list[str]


def validate_scientific_output(items: list[ScientificItem], *, commerce_boosted: bool = False) -> ValidationResult:
    violations: list[str] = []
    if commerce_boosted:
        violations.append("commerce_cannot_change_scientific_rank")
    for item in items:
        blob = item.statement.lower()
        if any(token in blob for token in FORBIDDEN_DIAGNOSTIC):
            violations.append(f"{item.id}:diagnostic_language")
        if item.item_type is not ScientificItemType.GAP and not item.provenance:
            violations.append(f"{item.id}:missing_provenance")
        if item.evidence_strength and item.case_confidence and item.evidence_strength == item.case_confidence:
            if item.item_type is ScientificItemType.SYSTEM_INFERENCE:
                violations.append(f"{item.id}:strength_collapsed_into_confidence")
    return ValidationResult(accepted=not violations, violations=violations)


def item_from_mapping(payload: dict[str, Any]) -> ScientificItem:
    return ScientificItem(
        id=str(payload["id"]),
        version=str(payload.get("version") or "1"),
        item_type=ScientificItemType(payload["item_type"]),
        statement=str(payload["statement"]),
        provenance=list(payload.get("provenance") or []),
        evidence_strength=payload.get("evidence_strength"),
        case_confidence=payload.get("case_confidence"),
        supports=list(payload.get("supports") or []),
        weakens=list(payload.get("weakens") or []),
        does_not_address=list(payload.get("does_not_address") or []),
        gaps=list(payload.get("gaps") or []),
        safety_constraints=list(payload.get("safety_constraints") or []),
        rationale=str(payload.get("rationale") or ""),
        last_evaluated_at=payload.get("last_evaluated_at"),
    )
