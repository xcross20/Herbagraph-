"""Parser benchmark grades real classify_document output against independent fixtures."""

from __future__ import annotations

from app.discovery.parser_benchmark import grade_case, load_cases
from app.discovery.telemetry import snapshot


def test_parser_benchmark_grades_real_classifier():
    failures = []
    for case in load_cases():
        score = grade_case(case)
        if not score.passed:
            failures.extend(score.failures)
    assert not failures, failures


def test_unsupported_document_increments_tripwire():
    before = snapshot().get("document_classified_unsupported", 0)
    from app.discovery.records import classify_document

    assert classify_document("labs.pdf", "%PDF-1.4 unreadable binary junk") == "unsupported"
    assert snapshot().get("document_classified_unsupported", 0) >= before + 1
