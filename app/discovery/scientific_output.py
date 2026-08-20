"""Scientific-output contract and validator (Milestone 6)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.discovery.telemetry import increment
from app.models.enums import ScientificItemType

FORBIDDEN_DIAGNOSTIC = (
    "you have",
    "this confirms",
    "this proves",
    "diagnosis is",
    "disease probability",
    "this is anxiety",
    "you definitely have",
    "probability of disease",
)
FORBIDDEN_CAUSAL = (
    "this caused",
    "caused your",
    "proves that",
    "because you took",
    "the herb cured",
    "this treatment worked because",
)
COVERAGE_MISUSE = (
    "rules out",
    "ruled out",
    "negative evidence that you do not",
    "emg rules out",
)
SAFE_LIMITATION = "I updated the Case. I will not write a diagnosis or an unsupported causal claim."


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
    citations: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    accepted: bool
    violations: list[str]
    replacement: str | None = None


def _has_disguised_probability(blob: str) -> bool:
    if re.search(r"\b\d{2,3}%", blob) and any(token in blob for token in ("likely", "chance", "probability", "diagnos")):
        return True
    return "likelihood of" in blob or "percent chance" in blob


def verify_citations(pmids: list[str], stored_pmids: set[str]) -> list[str]:
    violations: list[str] = []
    seen: set[str] = set()
    for pmid in pmids:
        token = str(pmid).replace("PMID:", "").strip()
        if not token:
            violations.append("citation_missing")
            continue
        if not token.isdigit():
            violations.append(f"citation_malformed:{token}")
            continue
        if token in seen:
            violations.append(f"citation_duplicate:{token}")
            continue
        seen.add(token)
        if token not in stored_pmids:
            violations.append(f"citation_unresolved:{token}")
    return violations


def validate_scientific_output(
    items: list[ScientificItem],
    *,
    commerce_boosted: bool = False,
    stored_pmids: set[str] | None = None,
    unknown_as_negative: bool = False,
) -> ValidationResult:
    violations: list[str] = []
    if commerce_boosted:
        violations.append("commerce_cannot_change_scientific_rank")
        increment("commerce_changed_scientific_rank")
    if unknown_as_negative:
        violations.append("unknown_coverage_as_negative")
        increment("unknown_coverage_as_negative")
    for item in items:
        blob = item.statement.lower()
        if any(token in blob for token in FORBIDDEN_DIAGNOSTIC) or _has_disguised_probability(blob):
            violations.append(f"{item.id}:diagnostic_language")
        if any(token in blob for token in FORBIDDEN_CAUSAL):
            violations.append(f"{item.id}:unsupported_causal_language")
        if any(token in blob for token in COVERAGE_MISUSE):
            violations.append(f"{item.id}:coverage_misuse")
        if item.item_type is not ScientificItemType.GAP and not item.provenance:
            violations.append(f"{item.id}:missing_provenance")
            increment("sourceless_scientific_output")
        if item.evidence_strength and item.case_confidence and item.evidence_strength == item.case_confidence:
            if item.item_type is ScientificItemType.SYSTEM_INFERENCE:
                violations.append(f"{item.id}:strength_collapsed_into_confidence")
        if item.citations:
            allowed = stored_pmids if stored_pmids is not None else set()
            for problem in verify_citations(item.citations, allowed):
                violations.append(f"{item.id}:{problem}")
    accepted = not violations
    if not accepted:
        increment("scientific_output_blocked")
    return ValidationResult(
        accepted=accepted,
        violations=violations,
        replacement=None if accepted else SAFE_LIMITATION,
    )


def fail_closed_text(statement: str, *, provenance: list[str] | None = None, citations: list[str] | None = None, stored_pmids: set[str] | None = None) -> str:
    check = validate_scientific_output(
        [
            ScientificItem(
                id="surface",
                version="1",
                item_type=ScientificItemType.SYSTEM_INFERENCE,
                statement=statement,
                provenance=list(provenance or ["discovery"]),
                citations=list(citations or []),
            )
        ],
        stored_pmids=stored_pmids,
    )
    if check.accepted:
        return statement
    return check.replacement or SAFE_LIMITATION


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
        citations=list(payload.get("citations") or []),
    )
