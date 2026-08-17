"""Independent scientific benchmark. Expected answers come from the spec fixture."""

from __future__ import annotations

from app.discovery.coverage_governor import assess_coverage
from app.discovery.scientific_benchmark import grade_case, load_cases


def test_benchmark_fixture_rejects_current_style_diagnosis():
    cases = {item["id"]: item for item in load_cases()}
    emg = cases["SF-EMG-01"]
    bad = {
        "statement": "You have small-fiber neuropathy.",
        "provenance": [],
        "coverage": {"emg_ncs": {"small_fiber_density": "does_not_directly_assess"}},
    }
    score = grade_case(emg, bad)
    assert score.passed is False
    assert any("forbidden" in item or "provenance" in item for item in score.failures)


def test_benchmark_accepts_spec_aligned_small_fiber_emg():
    cases = {item["id"]: item for item in load_cases()}
    emg = cases["SF-EMG-01"]
    good = {
        "statement": "A normal EMG does not assess small-fiber density. Small-fiber investigation remains open.",
        "provenance": ["coverage-governor-v1"],
        "coverage": {
            "emg_ncs": {
                "small_fiber_density": assess_coverage("emg_ncs", "small_fiber_density").relation.value
            }
        },
        "commerce_boosted": False,
    }
    score = grade_case(emg, good)
    assert score.passed is True, score.failures


def test_benchmark_unknown_biliary_emg_is_not_negative_evidence():
    cases = {item["id"]: item for item in load_cases()}
    case = cases["BIL-EMG-01"]
    observed = {
        "statement": "EMG is not evidence about biliary structure.",
        "provenance": ["coverage-governor-v1"],
        "coverage": {
            "emg_ncs": {"biliary_stones": assess_coverage("emg_ncs", "biliary_stones").relation.value}
        },
    }
    score = grade_case(case, observed)
    assert score.passed is True, score.failures
