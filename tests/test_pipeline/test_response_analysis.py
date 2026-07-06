from datetime import datetime, timezone

from app.models.enums import EvidenceLevel, LabResultStatus
from app.pipeline.response_analysis import (
    DISCLAIMER,
    build_evidence_context,
    compute_biomarker_change,
    compute_biomarker_changes,
    compute_biomarker_direction,
    compute_system_responses,
    generate_response_report,
)
from app.schemas.pipeline import NormalizedLabResult


def _result(name, value, unit="mg/L", status=LabResultStatus.HIGH):
    return NormalizedLabResult(
        biomarker_name=name,
        raw_test_name=name,
        value=value,
        unit=unit,
        reference_range_low=0.0,
        reference_range_high=3.0,
        status=status,
    )


class _EvidenceClaim:
    def __init__(self, summary, evidence_level, pmid=None):
        self.summary = summary
        self.evidence_level = evidence_level
        self.pmid = pmid


def test_compute_biomarker_direction_improved_toward_optimal():
    assert compute_biomarker_direction("CRP", 8.2, 1.5) == "improved"


def test_compute_biomarker_direction_worsened_away_from_optimal():
    assert compute_biomarker_direction("CRP", 1.0, 8.2) == "worsened"


def test_compute_biomarker_direction_unchanged_both_optimal():
    assert compute_biomarker_direction("CRP", 0.5, 0.6) == "unchanged"


def test_compute_biomarker_direction_unknown_for_untracked_biomarker():
    assert compute_biomarker_direction("Not A Real Biomarker", 1.0, 2.0) == "unknown"


def test_compute_biomarker_direction_handles_bidirectional_optimum():
    # Ferritin: unhealthy both too low and too high, must not naively assume "lower is better"
    assert compute_biomarker_direction("Ferritin", 8.0, 45.0) == "improved"


def test_compute_biomarker_change_computes_percent_change_and_direction():
    change = compute_biomarker_change("CRP", 3.6, 1.2, "mg/L")
    assert change["percent_change"] == -66.7
    assert change["direction"] == "improved"
    assert change["direction_label"] == "Improved"


def test_compute_biomarker_change_percent_change_none_when_baseline_zero():
    change = compute_biomarker_change("CRP", 0.0, 1.2, "mg/L")
    assert change["percent_change"] is None


def test_compute_biomarker_changes_pairs_by_name_and_sorts():
    baseline = [_result("CRP", 8.2), _result("Ferritin", 8.0, unit="ng/mL")]
    follow_up = [_result("CRP", 1.5), _result("Ferritin", 45.0, unit="ng/mL")]
    changes = compute_biomarker_changes(baseline, follow_up)
    assert [c["biomarker_name"] for c in changes] == ["CRP", "Ferritin"]


def test_compute_biomarker_changes_skips_biomarkers_missing_from_either_snapshot():
    baseline = [_result("CRP", 8.2), _result("Glucose", 90.0, unit="mg/dL")]
    follow_up = [_result("CRP", 1.5)]
    changes = compute_biomarker_changes(baseline, follow_up)
    assert [c["biomarker_name"] for c in changes] == ["CRP"]


def test_compute_system_responses_marks_improved_with_high_confidence_for_two_contributors():
    changes = compute_biomarker_changes(
        [_result("CRP", 8.2), _result("Ferritin", 8.0, unit="ng/mL")],
        [_result("CRP", 1.5), _result("Ferritin", 45.0, unit="ng/mL")],
    )
    responses = compute_system_responses(changes)
    inflammation = next(r for r in responses if r["system_code"] == "inflammation")
    assert inflammation["response"] == "improved"
    assert inflammation["confidence"] == "high"
    assert "CRP" in inflammation["contributing_biomarkers"]


def test_compute_system_responses_no_data_when_no_contributing_biomarkers():
    responses = compute_system_responses([])
    assert all(r["response"] == "no_data" for r in responses)
    assert all(r["confidence"] == "low" for r in responses)


def test_compute_system_responses_sorts_no_data_last():
    changes = compute_biomarker_changes([_result("CRP", 8.2)], [_result("CRP", 1.5)])
    responses = compute_system_responses(changes)
    no_data_flags = [r["response"] == "no_data" for r in responses]
    assert no_data_flags == sorted(no_data_flags)


def test_build_evidence_context_filters_claims_without_summary():
    claims = [
        _EvidenceClaim("Curcumin reduces inflammatory markers.", EvidenceLevel.MODERATE, "123"),
        _EvidenceClaim(None, EvidenceLevel.MODERATE),
    ]
    context = build_evidence_context("Curcumin", claims)
    assert len(context) == 1
    assert context[0]["intervention_name"] == "Curcumin"
    assert context[0]["pmid"] == "123"


def test_generate_response_report_contains_disclaimer_and_no_causal_claim():
    report = generate_response_report(
        intervention_name="Curcumin",
        baseline_results=[_result("CRP", 3.6)],
        follow_up_results=[_result("CRP", 1.2)],
        baseline_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        follow_up_date=datetime(2024, 2, 26, tzinfo=timezone.utc),
    )
    assert report["disclaimer"] == DISCLAIMER
    assert "does not infer causality" in report["disclaimer"]
    assert report["duration_days"] == 56
    assert report["biomarker_changes"][0]["direction"] == "improved"


def test_generate_response_report_duration_none_without_dates():
    report = generate_response_report(
        intervention_name="Curcumin",
        baseline_results=[_result("CRP", 3.6)],
        follow_up_results=[_result("CRP", 1.2)],
        baseline_date=None,
        follow_up_date=None,
    )
    assert report["duration_days"] is None
