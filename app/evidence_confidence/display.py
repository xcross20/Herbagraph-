"""Clinician-scannable evidence labels and evidence-first synthesis copy."""

from __future__ import annotations

from app.models.enums import EvidenceQualityGrade, EvidenceTier

EVIDENCE_DISPLAY_LABELS: dict[str, str] = {
    "high_human": "🟢 High Human Evidence",
    "moderate_human": "🟡 Moderate Human Evidence",
    "emerging": "🟠 Emerging Evidence",
    "mechanistic": "⚪ Mechanistic Only",
}

_INTERVENTION_CLASSES: dict[str, list[str]] = {
    "Iron": [
        "Iron supplementation",
        "Dietary iron optimization",
        "Evaluation for underlying causes of deficiency",
    ],
    "Curcumin": [
        "Curcuminoid supplementation",
        "Whole-food turmeric intake",
        "Anti-inflammatory dietary patterns",
    ],
    "Vitamin D3": [
        "Vitamin D repletion",
        "Sunlight and dietary vitamin D sources",
        "Monitoring 25-OH vitamin D response",
    ],
    "Methylfolate": [
        "Folate repletion",
        "Dietary folate optimization",
        "Assessment of B12 and homocysteine context",
    ],
    "Vitamin B12": [
        "B12 repletion",
        "Dietary B12 sources",
        "Evaluation for malabsorption causes",
    ],
}

_CATEGORY_CLASSES: dict[str, list[str]] = {
    "supplement": ["Targeted supplementation", "Dietary optimization", "Clinician-guided monitoring"],
    "herb": ["Botanical supplementation", "Whole-food sources", "Safety-aware clinician review"],
    "phytochemical": ["Isolated compound supplementation", "Whole-food sources", "Literature-informed dosing review"],
    "food": ["Dietary incorporation", "Nutrient density optimization", "Sustained intake patterns"],
    "exercise": ["Structured exercise protocol", "Progressive training plan", "Recovery and monitoring"],
    "sleep": ["Sleep hygiene optimization", "Behavioral sleep therapy", "Circadian rhythm support"],
    "stress_reduction": ["Stress-reduction practice", "Mind-body intervention", "HPA-axis supportive lifestyle"],
}


def evidence_display_label(
    quality_grade: EvidenceQualityGrade,
    evidence_tier: EvidenceTier | str | None = None,
) -> str:
    tier_val = evidence_tier.value if isinstance(evidence_tier, EvidenceTier) else (evidence_tier or "")
    if tier_val in (EvidenceTier.PRECLINICAL.value, EvidenceTier.RESEARCH_HYPOTHESIS.value):
        return EVIDENCE_DISPLAY_LABELS["mechanistic"]
    if quality_grade in (EvidenceQualityGrade.VERY_HIGH, EvidenceQualityGrade.HIGH):
        return EVIDENCE_DISPLAY_LABELS["high_human"]
    if tier_val == EvidenceTier.EMERGING.value or quality_grade == EvidenceQualityGrade.MODERATE:
        return EVIDENCE_DISPLAY_LABELS["emerging"]
    if quality_grade == EvidenceQualityGrade.LOW:
        return EVIDENCE_DISPLAY_LABELS["moderate_human"]
    return EVIDENCE_DISPLAY_LABELS["mechanistic"]


def intervention_classes(intervention_name: str, category: str) -> list[str]:
    if intervention_name in _INTERVENTION_CLASSES:
        return list(_INTERVENTION_CLASSES[intervention_name])
    return list(_CATEGORY_CLASSES.get(category, [
        "Evidence-informed intervention",
        "Lifestyle or dietary optimization",
        "Clinician-guided follow-up",
    ]))


def evidence_synthesis_statement(
    intervention_name: str,
    biomarker_names: list[str],
    display_label: str,
) -> str:
    biomarker_phrase = ", ".join(biomarker_names[:2]) if biomarker_names else "the observed biology"
    if "🟢" in display_label or "High Human" in display_label:
        strength = "Current evidence supports"
    elif "🟠" in display_label or "Emerging" in display_label:
        strength = "Emerging evidence suggests consideration of"
    elif "⚪" in display_label:
        strength = "Mechanistic and preliminary evidence relates to"
    else:
        strength = "Available evidence suggests consideration of"
    return (
        f"{strength} {intervention_name.lower()}-class approaches in the context of "
        f"{biomarker_phrase}. This is evidence synthesis, not a treatment directive."
    )