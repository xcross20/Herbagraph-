"""Deterministic hypothesis families and investigation groups.

This is not a diagnosis catalog. Each row is a *branch worth investigating*
with confirmatory markers and grouped tests. The engine never marks a family
ruled out or writes a diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HypothesisFamily:
    code: str
    label: str
    branch: str
    keywords: tuple[str, ...]
    resolution_markers: tuple[str, ...]
    supporting_markers: tuple[str, ...]
    core: tuple[str, ...]
    directed: tuple[str, ...]
    conditional: tuple[str, ...]
    why_not_a_diagnosis: str = (
        "Investigation relevance is not diagnostic certainty. "
        "This family deserves looking into; it is not a claim that the person has it."
    )
    notes: tuple[str, ...] = field(default_factory=tuple)


HYPOTHESIS_FAMILIES: tuple[HypothesisFamily, ...] = (
    HypothesisFamily(
        code="small_fiber_dysfunction",
        label="Small-fiber / peripheral sensory dysfunction",
        branch="peripheral_nerve",
        keywords=("burn", "burning", "tingl", "numb", "neuropath", "feet at night", "pins and needles"),
        resolution_markers=("Glucose", "HbA1c", "Vitamin B12", "MMA", "TSH"),
        supporting_markers=("Vitamin B12", "MCV", "Glucose", "HbA1c"),
        core=("Focused neurologic / sensory exam", "Fasting glucose", "Vitamin B12"),
        directed=("MMA", "HbA1c", "EMG/NCS status", "TSH"),
        conditional=("Skin biopsy if exam and labs remain unexplained", "Autonomic testing", "Autoimmune neuropathy panel"),
    ),
    HypothesisFamily(
        code="b12_functional_gap",
        label="B12 / one-carbon functional gap",
        branch="nutritional",
        keywords=("burn", "tingl", "numb", "neuropath", "fatigue", "vegan", "b12", "macrocyt"),
        resolution_markers=("Vitamin B12", "MMA", "Homocysteine", "MCV", "Folate"),
        supporting_markers=("Vitamin B12", "MCV", "Folate"),
        core=("Vitamin B12", "MCV", "Medication history (metformin, PPI)"),
        directed=("MMA", "Homocysteine", "Folate"),
        conditional=("Intrinsic-factor / parietal-cell antibodies if MMA stays high"),
    ),
    HypothesisFamily(
        code="glucose_dysregulation",
        label="Glucose / metabolic dysregulation",
        branch="metabolic",
        keywords=("burn", "neuropath", "thirst", "polyuria", "weight", "fatigue"),
        resolution_markers=("Glucose", "HbA1c", "Insulin"),
        supporting_markers=("Glucose", "HbA1c", "Insulin"),
        core=("Fasting glucose", "HbA1c"),
        directed=("Fasting insulin", "Repeat glucose if single value"),
        conditional=("OGTT if fasting and A1c disagree"),
    ),
    HypothesisFamily(
        code="thyroid_axis",
        label="Thyroid axis contribution",
        branch="thyroid",
        keywords=("fatigue", "cold", "weight", "hair", "constipat", "palpit"),
        resolution_markers=("TSH", "Free T4", "Free T3"),
        supporting_markers=("TSH", "Free T4"),
        core=("TSH", "Free T4"),
        directed=("Free T3", "TPO antibodies if TSH abnormal"),
        conditional=("Repeat TSH if discordant symptoms"),
    ),
    HypothesisFamily(
        code="iron_oxygen_delivery",
        label="Iron / oxygen-delivery gap",
        branch="nutritional",
        keywords=("fatigue", "breath", "dizzy", "restless", "hair"),
        resolution_markers=("Ferritin", "Iron", "TIBC", "Hemoglobin"),
        supporting_markers=("Ferritin", "Hemoglobin", "MCV"),
        core=("Ferritin", "CBC / hemoglobin"),
        directed=("Iron", "TIBC", "Transferrin saturation"),
        conditional=("CRP with ferritin if inflammation likely"),
    ),
    HypothesisFamily(
        code="inflammatory_signal",
        label="Systemic inflammatory signal",
        branch="inflammatory",
        keywords=("pain", "stiff", "swell", "fever", "inflamm"),
        resolution_markers=("CRP", "hs-CRP", "ESR"),
        supporting_markers=("CRP", "hs-CRP", "Ferritin"),
        core=("hs-CRP or CRP",),
        directed=("ESR", "Ferritin"),
        conditional=("Autoimmune serology if exam suggests"),
    ),
    HypothesisFamily(
        code="autoimmune_targeting",
        label="Autoimmune targeting",
        branch="autoimmune",
        keywords=("rash", "joint", "autoimmune", "ana", "thyroid"),
        resolution_markers=("ANA", "RF", "Anti-CCP", "TPO Antibodies"),
        supporting_markers=("ANA", "RF", "TSH"),
        core=("History of autoimmune disease", "ANA if systemic features"),
        directed=("RF / Anti-CCP if inflammatory arthritis", "TPO if thyroid pattern"),
        conditional=("Specialist serology only after phenotype match"),
    ),
    HypothesisFamily(
        code="toxic_or_exposure",
        label="Toxic / exposure contribution",
        branch="toxic_exposure",
        keywords=("expos", "solvent", "metal", "alcohol", "chemo"),
        resolution_markers=(),
        supporting_markers=(),
        core=("Exposure and medication history",),
        directed=("Targeted toxicology only if history is positive",),
        conditional=("Occupational referral"),
    ),
    HypothesisFamily(
        code="autonomic_involvement",
        label="Autonomic involvement",
        branch="autonomic",
        keywords=("dizzy", "faint", "sweat", "tachycard", "orthostat"),
        resolution_markers=("Glucose", "Vitamin B12", "TSH"),
        supporting_markers=("Glucose", "Vitamin B12"),
        core=("Orthostatic vitals", "Glucose", "B12"),
        directed=("Autonomic testing if orthostasis persists"),
        conditional=("Specialist autonomic lab"),
    ),
)

BRANCH_LABELS: dict[str, str] = {
    "peripheral_nerve": "Peripheral nerve",
    "nutritional": "Nutritional",
    "metabolic": "Metabolic",
    "thyroid": "Thyroid",
    "inflammatory": "Inflammatory",
    "autoimmune": "Autoimmune",
    "toxic_exposure": "Toxic / exposure",
    "autonomic": "Autonomic",
    "structural": "Structural",
}


def families_for_concern(concern: str) -> list[HypothesisFamily]:
    text = (concern or "").lower()
    if not text.strip():
        return []
    matched = [family for family in HYPOTHESIS_FAMILIES if any(key in text for key in family.keywords)]
    return matched or []
