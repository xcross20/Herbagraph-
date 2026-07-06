"""Stage 3: Pathway Mapper.

Maps each abnormal biomarker to one or more of the 16 biological pathways
with weighted activation scores, using ~45 biomarker-to-pathway rules.
"""

from app.models.enums import LabResultStatus, PathwayDirection
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation

_ABNORMAL_STATUSES = {
    LabResultStatus.CRITICAL_LOW,
    LabResultStatus.LOW,
    LabResultStatus.HIGH,
    LabResultStatus.CRITICAL_HIGH,
}

_SEVERITY_MULTIPLIER = {
    LabResultStatus.CRITICAL_LOW: 1.3,
    LabResultStatus.LOW: 1.0,
    LabResultStatus.HIGH: 1.0,
    LabResultStatus.CRITICAL_HIGH: 1.3,
}

_PATHWAY_NAMES = {
    "NF_KB": "NF-κB Inflammatory Signaling",
    "IL6_JAK_STAT3": "IL-6/JAK-STAT3 Signaling",
    "AMPK": "AMPK Energy Sensing",
    "INSULIN_PI3K_AKT": "Insulin/PI3K-Akt Signaling",
    "NRF2": "Nrf2 Antioxidant Response",
    "MTOR_AUTOPHAGY": "mTOR/Autophagy",
    "HPA_AXIS": "HPA Axis (Stress Response)",
    "THYROID_HPT": "Thyroid/HPT Axis",
    "HEPATIC_LIPID": "Hepatic Lipid Metabolism",
    "ONE_CARBON_METHYLATION": "One-Carbon/Methylation Cycle",
    "GLP1_INCRETINS": "GLP-1/Incretin Signaling",
    "MITOCHONDRIAL_NAD": "Mitochondrial NAD+ Metabolism",
    "IRON_HEPCIDIN": "Iron/Hepcidin Regulation",
    "PURINE_URIC_ACID": "Purine/Uric Acid Metabolism",
    "VITAMIN_D_RECEPTOR": "Vitamin D Receptor Signaling",
    "RENAL_FILTRATION": "Renal Filtration Function",
}

# Each rule: (biomarker_name, {triggering statuses}, pathway_code, weight, direction)
_PATHWAY_CONFIGS: list[tuple[str, set[LabResultStatus], str, float, PathwayDirection]] = [
    ("CRP", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.9, PathwayDirection.ACTIVATED),
    ("CRP", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.7, PathwayDirection.ACTIVATED),

    ("Homocysteine", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "ONE_CARBON_METHYLATION", 0.9,
     PathwayDirection.SUPPRESSED),
    ("Homocysteine", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.3,
     PathwayDirection.ACTIVATED),

    ("Glucose", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Glucose", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GLP1_INCRETINS", 0.5,
     PathwayDirection.SUPPRESSED),
    ("Glucose", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "AMPK", 0.4, PathwayDirection.SUPPRESSED),

    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.9,
     PathwayDirection.SUPPRESSED),
    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GLP1_INCRETINS", 0.5,
     PathwayDirection.SUPPRESSED),
    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Insulin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Insulin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MTOR_AUTOPHAGY", 0.4,
     PathwayDirection.ACTIVATED),

    ("Uric Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PURINE_URIC_ACID", 0.9,
     PathwayDirection.ACTIVATED),
    ("Uric Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.3,
     PathwayDirection.ACTIVATED),
    ("Uric Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.4,
     PathwayDirection.SUPPRESSED),

    ("LDL", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.9,
     PathwayDirection.ACTIVATED),
    ("LDL", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.4, PathwayDirection.SUPPRESSED),

    ("HDL", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HEPATIC_LIPID", 0.6,
     PathwayDirection.SUPPRESSED),
    ("HDL", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NRF2", 0.3, PathwayDirection.SUPPRESSED),

    ("Triglycerides", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.85,
     PathwayDirection.ACTIVATED),
    ("Triglycerides", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "AMPK", 0.3,
     PathwayDirection.SUPPRESSED),

    ("ALT", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.7,
     PathwayDirection.ACTIVATED),
    ("ALT", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.5, PathwayDirection.SUPPRESSED),

    ("AST", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.6,
     PathwayDirection.ACTIVATED),
    ("AST", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.4, PathwayDirection.SUPPRESSED),
    ("AST", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Vitamin D", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "VITAMIN_D_RECEPTOR", 0.9,
     PathwayDirection.SUPPRESSED),

    ("TSH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "THYROID_HPT", 0.8,
     PathwayDirection.SUPPRESSED),
    ("TSH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HPA_AXIS", 0.3, PathwayDirection.ACTIVATED),
    ("TSH", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "THYROID_HPT", 0.8,
     PathwayDirection.ACTIVATED),

    ("B12", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "ONE_CARBON_METHYLATION", 0.8,
     PathwayDirection.SUPPRESSED),

    ("Folate", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "ONE_CARBON_METHYLATION", 0.85,
     PathwayDirection.SUPPRESSED),

    ("Magnesium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "AMPK", 0.4,
     PathwayDirection.SUPPRESSED),
    ("Magnesium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "INSULIN_PI3K_AKT", 0.4,
     PathwayDirection.SUPPRESSED),
    ("Magnesium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "MTOR_AUTOPHAGY", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Ferritin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IRON_HEPCIDIN", 0.85,
     PathwayDirection.ACTIVATED),
    ("Ferritin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.3,
     PathwayDirection.ACTIVATED),
    ("Ferritin", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Ferritin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Vitamin D", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "VITAMIN_D_RECEPTOR", 0.5,
     PathwayDirection.ACTIVATED),

    ("Triglycerides", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.2,
     PathwayDirection.SUPPRESSED),

    ("Glucose", {LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.3, PathwayDirection.SUPPRESSED),

    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.2,
     PathwayDirection.ACTIVATED),

    ("LDL", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.2,
     PathwayDirection.ACTIVATED),

    ("Magnesium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "VITAMIN_D_RECEPTOR", 0.2,
     PathwayDirection.SUPPRESSED),
]


def map_pathways(normalized_results: list[NormalizedLabResult]) -> list[PathwayActivation]:
    """Map abnormal biomarkers to activated/suppressed pathways with weighted activation scores."""
    abnormal = {r.biomarker_name: r for r in normalized_results if r.status in _ABNORMAL_STATUSES}

    # pathway_code -> {"activated": float, "suppressed": float, "biomarkers": set[str]}
    accum: dict[str, dict] = {}

    for biomarker_name, statuses, pathway_code, weight, direction in _PATHWAY_CONFIGS:
        result = abnormal.get(biomarker_name)
        if result is None or result.status not in statuses:
            continue
        multiplier = _SEVERITY_MULTIPLIER[result.status]
        bucket = accum.setdefault(pathway_code, {"activated": 0.0, "suppressed": 0.0, "biomarkers": set()})
        bucket[direction.value] += weight * multiplier
        bucket["biomarkers"].add(biomarker_name)

    activations: list[PathwayActivation] = []
    for pathway_code, bucket in accum.items():
        net_activated = bucket["activated"]
        net_suppressed = bucket["suppressed"]
        if net_activated >= net_suppressed:
            direction = PathwayDirection.ACTIVATED
            score = net_activated
        else:
            direction = PathwayDirection.SUPPRESSED
            score = net_suppressed
        activations.append(
            PathwayActivation(
                pathway_code=pathway_code,
                pathway_name=_PATHWAY_NAMES[pathway_code],
                activation_score=min(score, 1.0),
                direction=direction,
                contributing_biomarkers=sorted(bucket["biomarkers"]),
            )
        )

    activations.sort(key=lambda a: a.activation_score, reverse=True)
    return activations
