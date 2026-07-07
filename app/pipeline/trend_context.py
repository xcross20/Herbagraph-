"""Lab trend context: compare current results to prior uploads for the same user."""

from __future__ import annotations

from app.pipeline.biomarker_normalizer import get_reference_data
from app.schemas.pipeline import NormalizedLabResult

_DIRECTION_IMPROVED = "improved"
_DIRECTION_WORSENED = "worsened"
_DIRECTION_UNCHANGED = "unchanged"
_EPSILON = 1e-6


def _distance_to_optimal(value: float, optimal_low: float, optimal_high: float, width: float) -> float:
    if optimal_low <= value <= optimal_high:
        return 0.0
    distance = min(abs(value - optimal_low), abs(value - optimal_high))
    return distance / width if width > 0 else distance


def _trend_direction(biomarker_name: str, prior_value: float, current_value: float) -> str:
    ref = get_reference_data(biomarker_name)
    if not ref or ref.get("optimal_low") is None or ref.get("optimal_high") is None:
        if abs(current_value - prior_value) <= _EPSILON:
            return _DIRECTION_UNCHANGED
        return _DIRECTION_WORSENED if abs(current_value) > abs(prior_value) else _DIRECTION_IMPROVED

    optimal_low, optimal_high = ref["optimal_low"], ref["optimal_high"]
    reference_low, reference_high = ref.get("reference_low"), ref.get("reference_high")
    width = (
        (reference_high - reference_low)
        if (reference_low is not None and reference_high is not None and reference_high > reference_low)
        else max(optimal_high - optimal_low, 1.0)
    )
    prior_distance = _distance_to_optimal(prior_value, optimal_low, optimal_high, width)
    current_distance = _distance_to_optimal(current_value, optimal_low, optimal_high, width)

    if current_distance < prior_distance - _EPSILON:
        return _DIRECTION_IMPROVED
    if current_distance > prior_distance + _EPSILON:
        return _DIRECTION_WORSENED
    return _DIRECTION_UNCHANGED


def build_trend_context(
    current_labs: list[NormalizedLabResult],
    prior_labs: list[NormalizedLabResult] | None,
    *,
    prior_report_date: str | None = None,
) -> dict:
    """Compare current biomarkers to a prior lab snapshot."""
    if not prior_labs:
        return {
            "has_prior_labs": False,
            "prior_report_date": None,
            "compared_biomarkers": 0,
            "trends": [],
            "summary": "No prior lab upload found for trend comparison.",
        }

    prior_by_name = {lab.biomarker_name: lab for lab in prior_labs}
    trends: list[dict] = []

    for current in current_labs:
        prior = prior_by_name.get(current.biomarker_name)
        if prior is None:
            continue
        if current.qualitative_label or prior.qualitative_label:
            continue
        direction = _trend_direction(current.biomarker_name, prior.value, current.value)
        delta = round(current.value - prior.value, 4)
        trends.append(
            {
                "biomarker_name": current.biomarker_name,
                "prior_value": prior.value,
                "current_value": current.value,
                "unit": current.unit or prior.unit,
                "delta": delta,
                "direction": direction,
                "prior_status": prior.status.value,
                "current_status": current.status.value,
            }
        )

    improved = sum(1 for t in trends if t["direction"] == _DIRECTION_IMPROVED)
    worsened = sum(1 for t in trends if t["direction"] == _DIRECTION_WORSENED)
    unchanged = sum(1 for t in trends if t["direction"] == _DIRECTION_UNCHANGED)

    if not trends:
        summary = "Prior labs exist but no overlapping numeric biomarkers were found for comparison."
    else:
        summary = (
            f"Compared {len(trends)} biomarkers to prior upload"
            + (f" ({prior_report_date})" if prior_report_date else "")
            + f": {improved} improved, {worsened} worsened, {unchanged} unchanged."
        )

    return {
        "has_prior_labs": True,
        "prior_report_date": prior_report_date,
        "compared_biomarkers": len(trends),
        "improved_count": improved,
        "worsened_count": worsened,
        "unchanged_count": unchanged,
        "trends": sorted(trends, key=lambda t: (t["direction"] != _DIRECTION_WORSENED, t["biomarker_name"])),
        "summary": summary,
    }


def prior_labs_from_results(lab_results) -> list[NormalizedLabResult]:
    """Convert persisted LabResult rows to NormalizedLabResult for trend comparison."""
    from app.schemas.pipeline import NormalizedLabResult

    return [
        NormalizedLabResult(
            biomarker_name=r.biomarker_name,
            raw_test_name=r.raw_test_name or r.biomarker_name,
            value=r.value,
            unit=r.unit,
            reference_range_low=r.reference_range_low,
            reference_range_high=r.reference_range_high,
            status=r.status,
        )
        for r in lab_results
    ]