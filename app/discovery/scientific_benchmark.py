"""Grade structured output against independent expected answers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "benchmarks" / "scientific" / "v1" / "cases.json"


@dataclass(frozen=True)
class BenchmarkScore:
    case_id: str
    passed: bool
    failures: tuple[str, ...]


def load_cases(path: Path = DEFAULT_FIXTURE) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["cases"])


def grade_case(expected: dict, observed: dict) -> BenchmarkScore:
    failures: list[str] = []
    text = " ".join(
        [
            str(observed.get("statement") or ""),
            " ".join(observed.get("must_entail") or []),
            json.dumps(observed, default=str),
        ]
    ).lower()
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
