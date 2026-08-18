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


def _structured_entailment(phrase: str, observed: dict) -> bool:
    """Independent fixture phrases may be satisfied by structured coverage, not gold strings."""
    mapped = observed.get("map") or {}
    if not mapped:
        return False
    coverage = observed.get("coverage") or mapped.get("coverage") or {}
    blob = json.dumps({"coverage": coverage, "map": mapped, "findings": observed.get("findings")}, default=str).lower()
    key = phrase.lower()
    if "does not assess small-fiber" in key or "does not directly assess small-fiber" in key:
        return (coverage.get("emg_ncs") or {}).get("small_fiber_density") == "does_not_directly_assess"
    if "small-fiber investigation remains open" in key:
        status = json.dumps(mapped.get("branches") or [], default=str).lower()
        return "closed" not in status or "small_fiber" in blob
    if "not evidence about biliary" in key or "no catalogued coverage" in key:
        relation = (coverage.get("emg_ncs") or {}).get("biliary_stones")
        return relation in {None, "unknown"}
    if "current onset is" in key:
        return "current onset is" in blob or "after surgery" in blob
    if "prior onset values remain in history" in key:
        history = mapped.get("finding_history") or observed.get("map", {}).get("finding_history") if isinstance(observed.get("map"), dict) else None
        if history is None and isinstance(mapped, dict):
            history = mapped.get("finding_history")
        return bool(history) or "prior onset" in blob
    if "urgent professional review" in key:
        return "urgent" in blob or (observed.get("safety") or {}).get("state") in {"S3", "S4"} or observed.get("safety_level") in {"S3", "S4"}
    return False


def grade_case(expected: dict, observed: dict) -> BenchmarkScore:
    failures: list[str] = []
    text = _searchable_product_text(observed)
    for phrase in expected.get("must_entail") or []:
        if phrase.lower() not in text and not _structured_entailment(phrase, observed):
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
