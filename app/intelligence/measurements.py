"""Measurement / Coverage Engine adapter.

Wraps: app.discovery.coverage_governor, app.discovery.coverage_catalog
Contract: docs/personal-evidence/REASONING_CORE_ARCHITECTURE.md §3.2

Coverage semantics (from ADR-MVP-002):
  - DIRECTLY_ASSESSES       → test fully addresses a concept
  - PARTIALLY_ASSESSES      → test only partially addresses (limitation stated)
  - INDIRECTLY_INFORMS      → can indirectly inform
  - DOES_NOT_DIRECTLY_ASSESS → test does not address this concept
  - NOT_APPLICABLE          → catalogued as not applicable
  - UNKNOWN                 → no coverage relation catalogued

Coverage is epistemic completeness, NOT disease probability.
A test that does NOT directly assess a branch CANNOT close that branch.
An assay may partially assess a parent concept; it cannot close the parent by identity alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Delegation ──────────────────────────────────────────────────────────────

from app.discovery.coverage_governor import (  # noqa: E402
    assess_coverage as _assess_coverage,
    CoverageAssessment,
)
from app.discovery.coverage_catalog import (  # noqa: E402
    CatalogRelation,
    load_catalog as _load_catalog,
    catalog_version as _catalog_version,
    explain_relation as _explain,
)

# ── Re-export enum ────────────────────────────────────────────────────────

from app.models.enums import CoverageRelation  # noqa: E402


# ── Public API ──────────────────────────────────────────────────────────────


def assess_coverage(
    test_code: str,
    investigation_concept: str,
    protocol_id: str | None = None,
) -> CoverageAssessment:
    """
    Assess what a test or assay measures with respect to an investigation concept.

    Returns a CoverageAssessment with:
      - relation: CoverageRelation enum value
      - explanation: human-readable template string
      - test_code, concept, protocol_code
      - rule_version, provenance

    When no rule exists, returns UNKNOWN relation and calls the tripwire.
    """
    return _assess_coverage(test_code, investigation_concept, protocol_id)


def explain_coverage(
    test_name: str,
    concept_label: str,
    relation: CoverageRelation | str,
) -> str:
    """Return a human-readable explanation for a coverage relation."""
    return _explain(
        test_name=test_name,
        concept_label=concept_label,
        relation=str(relation.value) if hasattr(relation, "value") else str(relation),
    )


def catalog_version() -> str:
    """Return the version string of the loaded coverage catalog."""
    return _catalog_version()


def test_known(test_code: str) -> bool:
    """True when test_code is in the coverage catalog."""
    catalog = _load_catalog()
    return any(t.code == test_code for t in catalog.tests)


def concept_coverage_for_case(
    case_branch_code: str,
) -> list[CatalogRelation]:
    """
    Return all coverage relations for the concepts relevant to a given branch.

    Used by Personal Evidence modules to understand what a prior test addressed.
    """
    catalog = _load_catalog()
    branch_concepts = catalog.branch_concepts.get(case_branch_code, ())
    relations: list[CatalogRelation] = []
    seen: set[tuple[str, str]] = set()
    for rel in catalog.relations:
        if rel.concept in branch_concepts:
            key = (rel.test_code, rel.concept)
            if key not in seen:
                seen.add(key)
                relations.append(rel)
    return relations
