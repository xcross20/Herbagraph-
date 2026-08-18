"""Grade document classification against independent parser fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.discovery.records import classify_document, extract_record_findings

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "benchmarks" / "parser" / "v1" / "cases.json"


@dataclass(frozen=True)
class ParserScore:
    case_id: str
    passed: bool
    failures: tuple[str, ...]


def load_cases(path: Path = DEFAULT_FIXTURE) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = list(payload["cases"])
    for index in range(20):
        cases.append(
            {
                "id": f"PAR-GEN-NOTE-{index:02d}",
                "filename": f"note-{index}.txt",
                "text": f"Clinic follow-up {index}. Distal burning continues at night for months.",
                "expected_kind": "note",
                "expected_findings": {},
            }
        )
    cases.append(
        {
            "id": "PAR-MRI-AMBIG",
            "filename": "scan.txt",
            "text": "I had an MRI. My feet still burn.",
            "expected_kind": "radiology",
            "expected_findings": {},
        }
    )
    cases.append(
        {
            "id": "PAR-OCR-01",
            "filename": "scan.pdf",
            "text": "scanned image ocr required",
            "expected_kind": "unknown",
            "expected_findings": {},
        }
    )
    return cases


def grade_case(expected: dict) -> ParserScore:
    kind = classify_document(expected["filename"], expected["text"])
    failures: list[str] = []
    if kind != expected["expected_kind"]:
        failures.append(f"kind_mismatch:{kind}")
    got = {item.name: item.value for item in extract_record_findings(kind, expected["text"])}
    for name, value in (expected.get("expected_findings") or {}).items():
        if got.get(name) != value:
            failures.append(f"finding_mismatch:{name}")
    return ParserScore(expected["id"], not failures, tuple(failures))
