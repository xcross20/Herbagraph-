"""Versioned coverage catalog. Explanations come from relation templates, not gold phrases."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.models.enums import CoverageRelation

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "coverage_catalog_v1.json"

RELATION_TEMPLATES = {
    CoverageRelation.DIRECTLY_ASSESSES.value: "{test} directly assesses {concept}.",
    CoverageRelation.PARTIALLY_ASSESSES.value: "{test} only partially assesses {concept}.",
    CoverageRelation.INDIRECTLY_INFORMS.value: "{test} can indirectly inform {concept}.",
    CoverageRelation.DOES_NOT_DIRECTLY_ASSESS.value: "{test} does not directly assess {concept}.",
    CoverageRelation.NOT_APPLICABLE.value: "{test} is catalogued as not applicable to {concept}.",
    CoverageRelation.UNKNOWN.value: "No coverage relation is catalogued for {test} and {concept}.",
}


def normalize_label(raw: str) -> str:
    stripped = []
    for char in raw or "":
        if unicodedata.category(char) in {"Cf", "Mn"}:
            continue
        stripped.append(char)
    return " ".join("".join(stripped).lower().replace("/", " ").replace("-", " ").split())


@dataclass(frozen=True)
class CatalogTest:
    code: str
    name: str
    aliases: tuple[str, ...]
    finding_names: tuple[str, ...] = ()
    body_sites: tuple[str, ...] = ()
    modalities: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogConcept:
    code: str
    label: str
    body_site: str | None = None


@dataclass(frozen=True)
class CatalogRelation:
    test_code: str
    concept: str
    relation: str
    explanation: str
    protocol: str | None = None
    provenance: str = ""
    version: str = "coverage-catalog-v1"


@dataclass(frozen=True)
class CoverageCatalog:
    version: str
    tests: tuple[CatalogTest, ...]
    concepts: tuple[CatalogConcept, ...]
    relations: tuple[CatalogRelation, ...]
    branch_concepts: dict[str, tuple[str, ...]]
    body_sites: tuple[dict, ...]
    modalities: tuple[dict, ...]
    provenance: dict


def explain_relation(*, test_name: str, concept_label: str, relation: str) -> str:
    template = RELATION_TEMPLATES.get(relation, RELATION_TEMPLATES[CoverageRelation.UNKNOWN.value])
    return template.format(test=test_name, concept=concept_label)


def _load_raw(path: Path = CATALOG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load_catalog(path: str | None = None) -> CoverageCatalog:
    raw = _load_raw(Path(path) if path else CATALOG_PATH)
    version = str(raw.get("version") or "coverage-catalog-v1")
    concepts = tuple(
        CatalogConcept(code=item["code"], label=item["label"], body_site=item.get("body_site"))
        for item in raw.get("concepts") or []
    )
    concept_labels = {item.code: item.label for item in concepts}
    tests = tuple(
        CatalogTest(
            code=item["code"],
            name=item["name"],
            aliases=tuple(item.get("aliases") or ()),
            finding_names=tuple(item.get("finding_names") or ()),
            body_sites=tuple(item.get("body_sites") or ()),
            modalities=tuple(item.get("modalities") or ()),
        )
        for item in raw.get("tests") or []
    )
    test_names = {item.code: item.name for item in tests}
    relations = tuple(
        CatalogRelation(
            test_code=item["test_code"],
            concept=item["concept"],
            relation=item["relation"],
            explanation=explain_relation(
                test_name=test_names.get(item["test_code"], item["test_code"]),
                concept_label=concept_labels.get(item["concept"], item["concept"]),
                relation=item["relation"],
            ),
            protocol=item.get("protocol"),
            provenance=str(item.get("provenance") or ""),
            version=version,
        )
        for item in raw.get("rules") or []
    )
    branch_concepts = {
        key: tuple(values) for key, values in (raw.get("branch_concepts") or {}).items()
    }
    return CoverageCatalog(
        version=version,
        tests=tests,
        concepts=concepts,
        relations=relations,
        branch_concepts=branch_concepts,
        body_sites=tuple(raw.get("body_sites") or ()),
        modalities=tuple(raw.get("modalities") or ()),
        provenance=dict(raw.get("provenance") or {}),
    )


def catalog_version() -> str:
    return load_catalog().version


def tests_by_normalized_alias() -> dict[str, list[CatalogTest]]:
    index: dict[str, list[CatalogTest]] = {}
    for test in load_catalog().tests:
        keys = {
            normalize_label(test.code),
            normalize_label(test.name),
            *(normalize_label(alias) for alias in test.aliases),
            *(normalize_label(name) for name in test.finding_names),
        }
        for key in keys:
            if not key:
                continue
            index.setdefault(key, []).append(test)
    return index


def test_code_for_finding(name: str) -> str | None:
    key = normalize_label(name)
    matches = tests_by_normalized_alias().get(key) or []
    unique = {item.code: item for item in matches}
    if len(unique) == 1:
        return next(iter(unique))
    return None


def concepts_for_branch(branch_or_code: str) -> tuple[str, ...]:
    catalog = load_catalog()
    return catalog.branch_concepts.get(branch_or_code or "", ())


def concept_label(code: str) -> str:
    for item in load_catalog().concepts:
        if item.code == code:
            return item.label
    return code


def test_name(code: str) -> str:
    for item in load_catalog().tests:
        if item.code == code:
            return item.name
    return code


def __getattr__(name: str):
    if name == "TESTS":
        return load_catalog().tests
    if name == "RELATIONS":
        return load_catalog().relations
    raise AttributeError(name)
