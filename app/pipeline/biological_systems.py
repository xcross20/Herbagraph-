"""User-facing rollup of the 16 internal pathways into 7 biological systems.

Internally the pipeline reasons over 16 pathways (see pathway_mapper.py) -- that
granularity is useful for evidence retrieval and confidence scoring, but showing a
patient 16 pathway codes is neither actionable nor easy to interpret. This module
aggregates them into a small, stable set of "biological systems" with a simple 0-3
signal score.

Terminology is deliberate: outputs are phrased as an "evidence-weighted pathway
signal", never an "activation score" -- HerbaGraph has not directly measured
biological activation, only inferred a signal from lab values and published
mechanism-of-action literature.
"""

from app.models.enums import PathwayDirection
from app.schemas.pipeline import PathwayActivation

# system_code -> pathway codes that roll up into it. A pathway can inform more than one
# system (e.g. HEPATIC_LIPID matters for both cardiovascular risk and liver stress;
# NRF2 matters for both liver stress and oxidative/mitochondrial resilience) -- systems
# are lenses on the same 16 pathways, not a disjoint partition of them.
SYSTEM_PATHWAYS: dict[str, list[str]] = {
    "inflammation": [
        "NF_KB",
        "IL6_JAK_STAT3",
        "FOOD_ANTIGEN_EXPOSURE",
        "IGE_SENSITIZATION",
        "AUTOIMMUNE_TARGETING",
        "PATHOGEN_BURDEN",
        "URINARY_PATHOGEN",
        "RESPIRATORY_PATHOGEN",
        "BIOFILM_ADHESION",
        "GASTRIC_COLONIZATION",
    ],
    "metabolic_health": ["INSULIN_PI3K_AKT", "GLP1_INCRETINS", "AMPK"],
    "cardiovascular_risk": ["HEPATIC_LIPID", "PURINE_URIC_ACID", "RENAL_FILTRATION"],
    "liver_detox_stress": ["HEPATIC_LIPID", "NRF2", "HEPATOTROPIC_VIRAL"],
    "nutrient_status": [
        "ONE_CARBON_METHYLATION",
        "IRON_HEPCIDIN",
        "VITAMIN_D_RECEPTOR",
        "NUTRIENT_DEFICIENCY",
        "GI_MUCOSAL_BARRIER",
    ],
    "thyroid_endocrine": ["THYROID_HPT", "HPA_AXIS"],
    "oxidative_stress_mitochondrial": ["NRF2", "MTOR_AUTOPHAGY", "MITOCHONDRIAL_NAD"],
}

SYSTEM_NAMES: dict[str, str] = {
    "inflammation": "Inflammation",
    "metabolic_health": "Metabolic Health",
    "cardiovascular_risk": "Cardiovascular Risk",
    "liver_detox_stress": "Liver Detox/Stress",
    "nutrient_status": "Nutrient Status",
    "thyroid_endocrine": "Thyroid/Endocrine",
    "oxidative_stress_mitochondrial": "Oxidative Stress / Mitochondrial Resilience",
}

SIGNAL_LABELS: dict[int, str] = {0: "No Signal", 1: "Mild Signal", 2: "Moderate Signal", 3: "Strong Signal"}


def _signal_level(pathways: list[PathwayActivation]) -> int:
    """0 (no signal) - 3 (strong signal), from:
    biomarker abnormality strength + number of supporting biomarkers
    + evidence quality/clinical relevance (the latter two are already baked into each
    pathway's activation_score, itself a rule-weight * severity-multiplier)."""
    if not pathways:
        return 0

    points = 0
    max_score = max(p.activation_score for p in pathways)
    all_biomarkers = {b for p in pathways for b in p.contributing_biomarkers}

    if max_score >= 0.7:
        points += 3
    elif max_score >= 0.4:
        points += 2
    elif max_score > 0.0:
        points += 1

    if len(all_biomarkers) >= 2:
        points += 1

    return min(points, 3)


def _direction(pathways: list[PathwayActivation]) -> str:
    activated = sum(p.activation_score for p in pathways if p.direction == PathwayDirection.ACTIVATED)
    suppressed = sum(p.activation_score for p in pathways if p.direction == PathwayDirection.SUPPRESSED)
    if activated == 0 and suppressed == 0:
        return "none"
    if activated > 0 and suppressed > 0:
        return "mixed"
    return "elevated" if activated > suppressed else "reduced"


def _confidence(pathways: list[PathwayActivation]) -> str:
    if not pathways:
        return "low"
    max_score = max(p.activation_score for p in pathways)
    num_biomarkers = len({b for p in pathways for b in p.contributing_biomarkers})
    if num_biomarkers >= 2 and max_score >= 0.6:
        return "high"
    if num_biomarkers >= 1 and max_score >= 0.3:
        return "moderate"
    return "low"


def compute_biological_systems(pathway_activations: list[PathwayActivation]) -> list[dict]:
    """Roll the internal 16-pathway activation list up into the 7 user-facing systems.

    Always returns all 7 systems (including ones with no signal), sorted by
    signal_level descending, so the shape of the output is stable regardless of
    which/how many biomarkers were abnormal.
    """
    by_code = {a.pathway_code: a for a in pathway_activations}

    systems = []
    for system_code, pathway_codes in SYSTEM_PATHWAYS.items():
        matched = [by_code[code] for code in pathway_codes if code in by_code]
        signal_level = _signal_level(matched)
        drivers = sorted({b for p in matched for b in p.contributing_biomarkers})

        systems.append(
            {
                "system_code": system_code,
                "system_name": SYSTEM_NAMES[system_code],
                "signal_level": signal_level,
                "signal_label": SIGNAL_LABELS[signal_level],
                "direction": _direction(matched),
                "confidence": _confidence(matched),
                "drivers": drivers,
                "pathways": [
                    {"pathway_code": p.pathway_code, "pathway_name": p.pathway_name} for p in matched
                ],
            }
        )

    systems.sort(key=lambda s: s["signal_level"], reverse=True)
    return systems
