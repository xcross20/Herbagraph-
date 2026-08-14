"""Independent confidence dimensions — not one opaque percentage.

evidence_confidence  — strength of the cited science
patient_match        — how well this patient's phenotype fits that science
data_sufficiency     — completeness of the workup (not the same as conclusion confidence)
decision_confidence  — whether this is a reasonable next action given the three above

Decision bands follow AHRQ-style thresholds: act, investigate, or stop.
The engine must never recommend tests solely to push a score over 0.90.
"""

from __future__ import annotations

from app.evidence_confidence.resolution_markers import (
    marker_is_present,
    present_marker_keys,
    resolution_markers_for,
)
from app.schemas.explainability import (
    ConfidenceDecomposition,
    ConfidenceGapItem,
    ScoreDimension,
)

DECOMPOSITION_VERSION = "decomposition_v1"

# Patient-context slots we can actually observe on HealthProfile today.
CONTEXT_SLOTS: tuple[tuple[str, str], ...] = (
    ("age_range", "Age"),
    ("biological_sex", "Biological sex"),
    ("current_medications", "Medication history"),
    ("known_conditions", "Prior diagnoses"),
    ("current_supplements", "Current supplements"),
    ("health_goals", "Goals or presenting concerns"),
)

# Clinically relevant context the profile cannot store yet — still a sufficiency gap.
UNMODELED_CONTEXT: tuple[str, ...] = (
    "Symptom timing and character",
    "Diet pattern",
    "Imaging / electrophysiology already done",
    "Physical exam findings",
)

ACTION_DECISION_MIN = 0.70
ACTION_SUFFICIENCY_MIN = 0.35
STOP_SUFFICIENCY_MIN = 0.80
STOP_DECISION_MAX = 0.55

# Transparent expected-gain table (not a learned model).
GAIN_MISSING_MARKER = 0.04
GAIN_MISSING_MEDS = 0.04
GAIN_MISSING_AGE_OR_SEX = 0.02
GAIN_MISSING_CONDITIONS = 0.03
GAIN_MISSING_SAFETY_LABS = 0.03
MAX_ADVERTISED_GAP = 0.18


def _slot_filled(health_profile: dict, key: str) -> bool:
    value = health_profile.get(key)
    if value is None or value == "":
        return False
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def _percent(score: float) -> int:
    return int(round(max(0.0, min(1.0, score)) * 100))


def _dimension(key: str, label: str, score: float, limiting: list[str]) -> ScoreDimension:
    clamped = round(max(0.0, min(1.0, score)), 4)
    return ScoreDimension(
        key=key,
        label=label,
        score=clamped,
        percent=_percent(clamped),
        limiting_factors=limiting[:6],
    )


def _patient_match(
    *,
    supporting_biomarker_names: list[str],
    present_lab_names: list[str],
    health_profile: dict,
    has_mechanism: bool,
) -> tuple[float, list[str]]:
    limiting: list[str] = []
    present = present_marker_keys(present_lab_names)
    support = supporting_biomarker_names or []
    if support:
        hit = sum(1 for name in support if marker_is_present(name, present))
        biomarker_fit = hit / len(support)
    else:
        biomarker_fit = 0.35
        limiting.append("No abnormal labs currently tie this intervention to the phenotype.")

    context_hits = 0
    context_total = 0
    for key, label in CONTEXT_SLOTS:
        if key in {"age_range", "biological_sex", "known_conditions", "current_medications"}:
            context_total += 1
            if _slot_filled(health_profile, key):
                context_hits += 1
            else:
                limiting.append(f"{label} is unknown, so population applicability is unverified.")
    context_fit = context_hits / context_total if context_total else 0.5
    mechanism_bonus = 0.08 if has_mechanism else 0.0
    score = 0.55 * biomarker_fit + 0.35 * context_fit + mechanism_bonus
    return score, limiting


def _data_sufficiency(
    *,
    intervention_name: str,
    pathway_codes: set[str],
    present_lab_names: list[str],
    health_profile: dict,
    has_safety_data: bool,
) -> tuple[float, list[str], list[str], list[str]]:
    present_keys = present_marker_keys(present_lab_names)
    expected = resolution_markers_for(intervention_name, pathway_codes)
    missing_markers: list[str] = []
    present_count = 0
    for marker in expected:
        if marker_is_present(marker, present_keys):
            present_count += 1
        else:
            missing_markers.append(marker)
    if expected:
        biomarker_resolution = present_count / len(expected)
    else:
        biomarker_resolution = 0.55

    missing_context: list[str] = []
    filled = 0
    for key, label in CONTEXT_SLOTS:
        if _slot_filled(health_profile, key):
            filled += 1
        else:
            missing_context.append(label)
    missing_context.extend(UNMODELED_CONTEXT)
    context_resolution = filled / len(CONTEXT_SLOTS)

    limiting: list[str] = []
    if missing_markers:
        limiting.append(
            "Insufficient biochemical resolution: " + ", ".join(missing_markers[:5])
        )
    if missing_context:
        limiting.append("Limited patient-context evidence: " + ", ".join(missing_context[:4]))
    if not has_safety_data:
        limiting.append("Safety catalog data for this intervention is thin.")

    score = 0.62 * biomarker_resolution + 0.38 * context_resolution
    return score, limiting, missing_markers, missing_context


def _decision_band(decision: float, sufficiency: float) -> tuple[str, str]:
    if sufficiency >= STOP_SUFFICIENCY_MIN and decision < STOP_DECISION_MAX:
        return (
            "stop",
            "The workup is relatively complete; remaining uncertainty is in the evidence, not missing data. More tests are unlikely to change management enough to justify burden.",
        )
    if decision >= ACTION_DECISION_MIN and sufficiency >= ACTION_SUFFICIENCY_MIN:
        return (
            "action",
            "There is enough concordant evidence and phenotype fit to consider this intervention class with a clinician — not a directive to take it.",
        )
    return (
        "investigate",
        "Named gaps could materially change the decision. Further testing is useful only when a result would change management.",
    )


def _gap_analysis(
    *,
    missing_markers: list[str],
    health_profile: dict,
    present_lab_names: list[str],
    has_safety_data: bool,
) -> list[ConfidenceGapItem]:
    items: list[ConfidenceGapItem] = []
    present_keys = present_marker_keys(present_lab_names)

    for marker in missing_markers[:6]:
        items.append(
            ConfidenceGapItem(
                action=f"Obtain {marker}",
                dimension="data_sufficiency",
                expected_gain=GAIN_MISSING_MARKER,
                expected_gain_percent=int(GAIN_MISSING_MARKER * 100),
            )
        )

    if not _slot_filled(health_profile, "current_medications"):
        items.append(
            ConfidenceGapItem(
                action="Confirm medication history",
                dimension="patient_match",
                expected_gain=GAIN_MISSING_MEDS,
                expected_gain_percent=int(GAIN_MISSING_MEDS * 100),
            )
        )
    if not _slot_filled(health_profile, "age_range") or not _slot_filled(health_profile, "biological_sex"):
        items.append(
            ConfidenceGapItem(
                action="Confirm age and biological sex",
                dimension="patient_match",
                expected_gain=GAIN_MISSING_AGE_OR_SEX,
                expected_gain_percent=int(GAIN_MISSING_AGE_OR_SEX * 100),
            )
        )
    if not _slot_filled(health_profile, "known_conditions"):
        items.append(
            ConfidenceGapItem(
                action="Record prior diagnoses",
                dimension="patient_match",
                expected_gain=GAIN_MISSING_CONDITIONS,
                expected_gain_percent=int(GAIN_MISSING_CONDITIONS * 100),
            )
        )

    safety_labs = ("Creatinine", "eGFR", "ALT", "AST")
    if has_safety_data and not any(marker_is_present(m, present_keys) for m in safety_labs):
        items.append(
            ConfidenceGapItem(
                action="Obtain kidney/liver safety labs (eGFR, ALT)",
                dimension="data_sufficiency",
                expected_gain=GAIN_MISSING_SAFETY_LABS,
                expected_gain_percent=int(GAIN_MISSING_SAFETY_LABS * 100),
            )
        )

    # Cap advertised total so we never imply a 90% hunt.
    total = 0.0
    capped: list[ConfidenceGapItem] = []
    for item in items:
        if total >= MAX_ADVERTISED_GAP:
            break
        remaining = MAX_ADVERTISED_GAP - total
        gain = min(item.expected_gain, remaining)
        capped.append(
            ConfidenceGapItem(
                action=item.action,
                dimension=item.dimension,
                expected_gain=round(gain, 4),
                expected_gain_percent=int(round(gain * 100)),
            )
        )
        total += gain
    return capped


def decompose_confidence(
    *,
    evidence_numeric: float,
    contradiction_penalty: float,
    supporting_biomarker_names: list[str],
    present_lab_names: list[str],
    pathway_codes: set[str],
    intervention_name: str,
    health_profile: dict | None,
    has_safety_data: bool,
    has_mechanism: bool,
    cited_human_studies: int = 0,
) -> ConfidenceDecomposition:
    """Build four independent scores plus a decision band and gap list."""
    profile = health_profile or {}
    evidence_limiting: list[str] = []
    if cited_human_studies == 0:
        evidence_limiting.append("Human clinical evidence is thin or absent in the cited set.")
    if contradiction_penalty >= 0.05:
        evidence_limiting.append("Cited studies include conflicting or null findings.")
    if evidence_numeric < 0.70:
        evidence_limiting.append("Study mix, recency, or quantity keeps evidence confidence below High.")

    match_score, match_limiting = _patient_match(
        supporting_biomarker_names=supporting_biomarker_names,
        present_lab_names=present_lab_names,
        health_profile=profile,
        has_mechanism=has_mechanism,
    )
    sufficiency_score, sufficiency_limiting, missing_markers, missing_context = _data_sufficiency(
        intervention_name=intervention_name,
        pathway_codes=pathway_codes,
        present_lab_names=present_lab_names,
        health_profile=profile,
        has_safety_data=has_safety_data,
    )

    # Decision is a blend, then capped when safety-relevant context is missing.
    decision = 0.40 * evidence_numeric + 0.35 * match_score + 0.25 * sufficiency_score
    if contradiction_penalty > 0:
        decision = max(0.0, decision - min(contradiction_penalty, 0.12))
    if not _slot_filled(profile, "current_medications") and has_safety_data:
        decision = min(decision, 0.78)
        sufficiency_limiting.append("Medication history missing — decision confidence is capped.")

    evidence_dim = _dimension("evidence_confidence", "Evidence confidence", evidence_numeric, evidence_limiting)
    match_dim = _dimension("patient_match", "Patient match", match_score, match_limiting)
    sufficiency_dim = _dimension("data_sufficiency", "Data sufficiency", sufficiency_score, sufficiency_limiting)
    decision_dim = _dimension("decision_confidence", "Decision confidence", decision, [])

    dims = {
        "evidence_quality": evidence_dim.score,
        "patient_context": match_dim.score,
        "biomarker_incompleteness": sufficiency_dim.score,
    }
    # If contradiction is material, that is its own bottleneck class.
    if contradiction_penalty >= 0.08:
        primary = "contradictory_evidence"
    else:
        primary = min(dims, key=dims.get)

    band, band_explanation = _decision_band(decision_dim.score, sufficiency_dim.score)
    gaps = _gap_analysis(
        missing_markers=missing_markers,
        health_profile=profile,
        present_lab_names=present_lab_names,
        has_safety_data=has_safety_data,
    )
    if band == "stop":
        gaps = []

    return ConfidenceDecomposition(
        evidence_confidence=evidence_dim,
        patient_match=match_dim,
        data_sufficiency=sufficiency_dim,
        decision_confidence=decision_dim,
        contradiction_penalty=round(contradiction_penalty, 4),
        primary_bottleneck=primary,
        decision_band=band,
        decision_band_explanation=band_explanation,
        missing_biomarkers=missing_markers,
        missing_context=missing_context,
        gap_analysis=gaps,
        formula_version=DECOMPOSITION_VERSION,
    )
