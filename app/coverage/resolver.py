"""Resolve a raw test name to a catalog test and optional protocol."""

from __future__ import annotations

from dataclasses import dataclass

from app.coverage.seed import TESTS, normalize_alias


@dataclass(frozen=True)
class CanonicalTestMatch:
    test_code: str
    canonical_name: str
    protocol_code: str | None
    confidence: float
    raw_name: str


def resolve_test(raw_name: str, protocol_text: str | None = None) -> CanonicalTestMatch | None:
    blob = normalize_alias(raw_name)
    if not blob:
        return None
    protocol_blob = normalize_alias(protocol_text or "")
    best: CanonicalTestMatch | None = None
    for test in TESTS:
        names = (test.code, test.name, *test.aliases)
        if any(normalize_alias(alias) in blob or blob in normalize_alias(alias) for alias in names):
            protocol = None
            confidence = 0.78
            for code, label in test.protocols:
                if protocol_blob and (normalize_alias(code) in protocol_blob or normalize_alias(label) in protocol_blob):
                    protocol = code
                    confidence = 0.92
                    break
            candidate = CanonicalTestMatch(
                test_code=test.code,
                canonical_name=test.name,
                protocol_code=protocol,
                confidence=confidence,
                raw_name=raw_name,
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate
    return best
