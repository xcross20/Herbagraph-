"""Grade structured output against independent expected answers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "benchmarks" / "scientific" / "v1" / "cases.json"
_PRODUCT_KEYS = ("statement", "provenance", "coverage", "findings", "map", "safety", "disclaimer")


@dataclass(frozen=True)
class BenchmarkScore:
    case_id: str
    passed: bool
    failures: tuple[str, ...]


def load_cases(path: Path = DEFAULT_FIXTURE) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["cases"])


def observed_from_product(case_payload: dict, map_payload: dict | None = None) -> dict:
    """Normalize Ask/API/map output. Expected labels stay in the fixture."""
    mapped = dict(map_payload or case_payload.get("investigation_map") or {})
    statement_parts = [
        case_payload.get("disclaimer") or "",
        json.dumps(case_payload.get("findings") or [], default=str),
        json.dumps(case_payload.get("hypotheses") or [], default=str),
        json.dumps(case_payload.get("safety") or {}, default=str),
        " ".join(mapped.get("coverage_notes") or []),
        " ".join(item.get("label") or "" for item in mapped.get("next_actions") or []),
        json.dumps(mapped.get("finding_history") or [], default=str),
        " ".join(str(item.get("text") or "") for item in case_payload.get("turns") or []),
    ]
    return {
        "statement": " ".join(str(item) for item in statement_parts if item),
        "provenance": list(mapped.get("provenance") or []),
        "coverage": mapped.get("coverage") or {},
        "commerce_boosted": bool(mapped.get("commerce_boosted") or case_payload.get("commerce_boosted")),
        "findings": case_payload.get("findings") or [],
        "map": mapped,
        "safety": case_payload.get("safety"),
        "disclaimer": case_payload.get("disclaimer"),
    }


def _searchable_product_text(observed: dict) -> str:
    chunks: list[str] = []
    for key in _PRODUCT_KEYS:
        value = observed.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            chunks.append(value)
        else:
            chunks.append(json.dumps(value, default=str))
    return " ".join(chunks).lower()


def grade_case(expected: dict, observed: dict) -> BenchmarkScore:
    failures: list[str] = []
    text = _searchable_product_text(observed)
    for phrase in expected.get("must_entail") or []:
        if phrase.lower() not in text:
            failures.append(f"missing_entailment:{phrase}")
    for phrase in expected.get("must_not_entail") or []:
        if phrase.lower() in text:
            failures.append(f"forbidden_entailment:{phrase}")
    if expected.get("required_provenance") and not observed.get("provenance"):
        failures.append("missing_provenance")
    if expected.get("commerce_neutral") and observed.get("commerce_boosted"):
        failures.append("commerce_not_neutral")
    coverage = expected.get("coverage") or {}
    observed_coverage = observed.get("coverage") or {}
    for test_code, targets in coverage.items():
        for concept, relation in targets.items():
            got = (observed_coverage.get(test_code) or {}).get(concept)
            if got != relation:
                failures.append(f"coverage_mismatch:{test_code}:{concept}")
    return BenchmarkScore(expected["id"], not failures, tuple(failures))
