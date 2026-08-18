"""Reject duplicate, contradictory, circular, or provenance-free coverage rules."""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.coverage_catalog import CoverageCatalog, load_catalog
from app.models.enums import CoverageRelation

LEGAL_RELATIONS = {item.value for item in CoverageRelation}


@dataclass(frozen=True)
class CatalogValidation:
    accepted: bool
    errors: tuple[str, ...]
    version: str


def validate_coverage_catalog(catalog: CoverageCatalog | None = None) -> CatalogValidation:
    catalog = catalog or load_catalog()
    errors: list[str] = []
    test_codes = {item.code for item in catalog.tests}
    concept_codes = {item.code for item in catalog.concepts}
    seen: dict[tuple[str, str, str | None], str] = {}

    if not catalog.version:
        errors.append("missing_catalog_version")
    if not catalog.provenance:
        errors.append("catalog_missing_provenance")

    for rule in catalog.relations:
        if rule.test_code not in test_codes:
            errors.append(f"unknown_test:{rule.test_code}")
        if rule.concept not in concept_codes:
            errors.append(f"unknown_concept:{rule.concept}")
        if rule.relation not in LEGAL_RELATIONS:
            errors.append(f"illegal_relation:{rule.test_code}:{rule.concept}:{rule.relation}")
        if not rule.provenance:
            errors.append(f"missing_provenance:{rule.test_code}:{rule.concept}")
        if rule.test_code == rule.concept:
            errors.append(f"circular_identity:{rule.test_code}")
        key = (rule.test_code, rule.concept, rule.protocol)
        prior = seen.get(key)
        if prior is None:
            seen[key] = rule.relation
        elif prior == rule.relation:
            errors.append(f"duplicate_rule:{rule.test_code}:{rule.concept}")
        else:
            errors.append(f"contradictory_rule:{rule.test_code}:{rule.concept}:{prior}!={rule.relation}")

    reverse = {(rule.concept, rule.test_code) for rule in catalog.relations}
    for rule in catalog.relations:
        if (rule.test_code, rule.concept) in reverse and rule.test_code != rule.concept:
            if any(
                other.test_code == rule.concept and other.concept == rule.test_code for other in catalog.relations
            ):
                errors.append(f"circular_pair:{rule.test_code}<->{rule.concept}")

    for branch, concepts in catalog.branch_concepts.items():
        for concept in concepts:
            if concept not in concept_codes:
                errors.append(f"branch_unknown_concept:{branch}:{concept}")

    unique_errors = tuple(dict.fromkeys(errors))
    return CatalogValidation(accepted=not unique_errors, errors=unique_errors, version=catalog.version)
