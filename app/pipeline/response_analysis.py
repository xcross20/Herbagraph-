"""Response Validation Module: compares a baseline lab snapshot against a later
follow-up snapshot for the same intervention.

This is deliberately *not* an ML/LLM feature -- it's arithmetic against each
biomarker's own reference/optimal range (the same data biomarker_normalizer
already uses), rolled up into the same 7 biological systems the rest of the
pipeline uses (see app.pipeline.biological_systems). No model infers whether the
intervention *caused* anything; it only summarizes what changed. See DISCLAIMER.
"""

from app.pipeline.biological_systems import SYSTEM_NAMES, SYSTEM_PATHWAYS
from app.pipeline.biomarker_normalizer import get_reference_data
from app.pipeline.pathway_mapper import get_pathways_for_biomarker

DISCLAIMER = (
    "The biomarker changes below are observed differences between two lab snapshots. "
    "This platform presents those changes alongside relevant published evidence about "
    "the tracked intervention, but it does not infer causality -- it cannot determine "
    "whether the intervention caused any change, whether another factor was "
    "responsible, or what would have happened without it."
)

_DIRECTION_LABELS = {
    "improved": "Improved",
    "worsened": "Worsened",
    "unchanged": "Unchanged",
    "unknown": "Unknown",
}

_EPSILON = 1e-9


def _distance_to_optimal(value: float, optimal_low: float, optimal_high: float, width: float) -> float:
    if optimal_low <= value <= optimal_high:
        return 0.0
    distance = min(abs(value - optimal_low), abs(value - optimal_high))
    return distance / width if width > 0 else distance


def compute_biomarker_direction(biomarker_name: str, baseline_value: float, follow_up_value: float) -> str:
    """"improved" | "worsened" | "unchanged" | "unknown" -- based on which value sits
    closer to the biomarker's own optimal range, not a naive "number went down/up"
    (many biomarkers, e.g. Ferritin or TSH, are unhealthy both too low and too high)."""
    ref = get_reference_data(biomarker_name)
    if not ref or ref.get("optimal_low") is None or ref.get("optimal_high") is None:
        return "unknown"

    optimal_low, optimal_high = ref["optimal_low"], ref["optimal_high"]
    reference_low, reference_high = ref.get("reference_low"), ref.get("reference_high")
    width = (
        (reference_high - reference_low)
        if (reference_low is not None and reference_high is not None and reference_high > reference_low)
        else max(optimal_high - optimal_low, 1.0)
    )

    baseline_distance = _distance_to_optimal(baseline_value, optimal_low, optimal_high, width)
    follow_up_distance = _distance_to_optimal(follow_up_value, optimal_low, optimal_high, width)

    if follow_up_distance < baseline_distance - _EPSILON:
        return "improved"
    if follow_up_distance > baseline_distance + _EPSILON:
        return "worsened"
    return "unchanged"


def compute_biomarker_change(
    biomarker_name: str, baseline_value: float, follow_up_value: float, unit: str | None
) -> dict:
    percent_change = (
        round((follow_up_value - baseline_value) / baseline_value * 100, 1) if baseline_value != 0 else None
    )
    direction = compute_biomarker_direction(biomarker_name, baseline_value, follow_up_value)
    return {
        "biomarker_name": biomarker_name,
        "baseline_value": baseline_value,
        "follow_up_value": follow_up_value,
        "unit": unit,
        "percent_change": percent_change,
        "direction": direction,
        "direction_label": _DIRECTION_LABELS[direction],
    }


def compute_biomarker_changes(baseline_results: list, follow_up_results: list) -> list[dict]:
    """Pair up baseline/follow-up NormalizedLabResult-like rows by biomarker_name and
    compute a change for every biomarker present in both snapshots."""
    baseline_by_name = {r.biomarker_name: r for r in baseline_results}
    follow_up_by_name = {r.biomarker_name: r for r in follow_up_results}

    changes = []
    for name, baseline in baseline_by_name.items():
        follow_up = follow_up_by_name.get(name)
        if follow_up is None:
            continue
        changes.append(compute_biomarker_change(name, baseline.value, follow_up.value, follow_up.unit))
    changes.sort(key=lambda c: c["biomarker_name"])
    return changes


def compute_system_responses(biomarker_changes: list[dict]) -> list[dict]:
    """Roll per-biomarker changes up into the same 7 biological systems used
    elsewhere, with an aggregate response (improved/worsened/mixed/unchanged/no_data)
    and a confidence based on how many biomarkers support that call."""
    changes_by_name = {c["biomarker_name"]: c for c in biomarker_changes}

    responses = []
    for system_code, pathway_codes in SYSTEM_PATHWAYS.items():
        pathway_codes_set = set(pathway_codes)
        contributing = [
            change
            for name, change in changes_by_name.items()
            if get_pathways_for_biomarker(name) & pathway_codes_set
        ]
        known = [c for c in contributing if c["direction"] != "unknown"]

        if not known:
            response = "no_data"
            confidence = "low"
        else:
            improved = sum(1 for c in known if c["direction"] == "improved")
            worsened = sum(1 for c in known if c["direction"] == "worsened")
            if improved > worsened:
                response = "improved"
            elif worsened > improved:
                response = "worsened"
            elif improved == worsened and improved > 0:
                response = "mixed"
            else:
                response = "unchanged"
            confidence = "high" if len(known) >= 2 else "moderate"

        responses.append(
            {
                "system_code": system_code,
                "system_name": SYSTEM_NAMES[system_code],
                "response": response,
                "response_label": response.replace("_", " ").title(),
                "confidence": confidence,
                "contributing_biomarkers": sorted(c["biomarker_name"] for c in known),
            }
        )

    responses.sort(key=lambda r: (r["response"] == "no_data", r["system_name"]))
    return responses


def build_evidence_context(intervention_name: str, evidence_claims: list) -> list[dict]:
    """Format seeded EvidenceClaim rows for the tracked intervention as read-only
    context alongside the observed changes -- never as a claim that the intervention
    caused them."""
    return [
        {
            "intervention_name": intervention_name,
            "summary": claim.summary,
            "evidence_level": claim.evidence_level.value,
            "pmid": claim.pmid,
        }
        for claim in evidence_claims
        if claim.summary
    ]


def generate_response_report(
    *,
    intervention_name: str,
    baseline_results: list,
    follow_up_results: list,
    baseline_date,
    follow_up_date,
    evidence_claims: list | None = None,
) -> dict:
    """Stage entry point: baseline + follow-up lab results -> a Biological Response Report."""
    biomarker_changes = compute_biomarker_changes(baseline_results, follow_up_results)
    system_responses = compute_system_responses(biomarker_changes)
    duration_days = (follow_up_date - baseline_date).days if baseline_date and follow_up_date else None

    return {
        "intervention_name": intervention_name,
        "baseline_date": baseline_date,
        "follow_up_date": follow_up_date,
        "duration_days": duration_days,
        "biomarker_changes": biomarker_changes,
        "system_responses": system_responses,
        "evidence_context": build_evidence_context(intervention_name, evidence_claims or []),
        "disclaimer": DISCLAIMER,
    }
