"""Category-based pathway rules for every biomarker in the global catalog.

Hand-tuned rules in pathway_mapper._PATHWAY_CONFIGS_CORE take precedence; this module
fills coverage gaps so every catalog biomarker maps to at least one pathway.
"""

from __future__ import annotations

from app.knowledge_graph.biomarker_catalog import REFERENCE_DATA
from app.models.enums import LabResultStatus, PathwayDirection

_HIGH = frozenset({LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH})
_LOW = frozenset({LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW})

# category -> list of (statuses, pathway_code, weight, direction)
_CATEGORY_RULES: dict[str, list[tuple[frozenset[LabResultStatus], str, float, PathwayDirection]]] = {
    "inflammatory": [
        (_HIGH, "NF_KB", 0.7, PathwayDirection.ACTIVATED),
        (_HIGH, "IL6_JAK_STAT3", 0.55, PathwayDirection.ACTIVATED),
    ],
    "metabolic": [
        (_HIGH, "INSULIN_PI3K_AKT", 0.75, PathwayDirection.SUPPRESSED),
        (_HIGH, "GLP1_INCRETINS", 0.45, PathwayDirection.SUPPRESSED),
        (_LOW, "INSULIN_PI3K_AKT", 0.65, PathwayDirection.SUPPRESSED),
        (_LOW, "MITOCHONDRIAL_NAD", 0.35, PathwayDirection.SUPPRESSED),
    ],
    "lipid": [
        (_HIGH, "HEPATIC_LIPID", 0.75, PathwayDirection.ACTIVATED),
        (_HIGH, "NRF2", 0.35, PathwayDirection.SUPPRESSED),
        (_LOW, "HEPATIC_LIPID", 0.45, PathwayDirection.SUPPRESSED),
    ],
    "hepatic": [
        (_HIGH, "HEPATIC_LIPID", 0.7, PathwayDirection.ACTIVATED),
        (_HIGH, "NRF2", 0.45, PathwayDirection.SUPPRESSED),
        (_LOW, "HEPATIC_LIPID", 0.4, PathwayDirection.SUPPRESSED),
    ],
    "renal": [
        (_HIGH, "RENAL_FILTRATION", 0.75, PathwayDirection.SUPPRESSED),
        (_LOW, "RENAL_FILTRATION", 0.55, PathwayDirection.SUPPRESSED),
    ],
    "electrolyte": [
        (_HIGH, "RENAL_FILTRATION", 0.5, PathwayDirection.SUPPRESSED),
        (_LOW, "RENAL_FILTRATION", 0.5, PathwayDirection.SUPPRESSED),
    ],
    "nutritional": [
        (_LOW, "NUTRIENT_DEFICIENCY", 0.85, PathwayDirection.SUPPRESSED),
        (_LOW, "ONE_CARBON_METHYLATION", 0.4, PathwayDirection.SUPPRESSED),
        (_HIGH, "NUTRIENT_DEFICIENCY", 0.35, PathwayDirection.ACTIVATED),
    ],
    "iron_metabolism": [
        (_LOW, "IRON_HEPCIDIN", 0.8, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.75, PathwayDirection.SUPPRESSED),
        (_HIGH, "IRON_HEPCIDIN", 0.7, PathwayDirection.ACTIVATED),
    ],
    "hormonal": [
        (_HIGH, "HPA_AXIS", 0.45, PathwayDirection.ACTIVATED),
        (_LOW, "HPA_AXIS", 0.45, PathwayDirection.SUPPRESSED),
        (_HIGH, "THYROID_HPT", 0.4, PathwayDirection.ACTIVATED),
        (_LOW, "THYROID_HPT", 0.4, PathwayDirection.SUPPRESSED),
    ],
    "cbc": [
        (_HIGH, "NF_KB", 0.4, PathwayDirection.ACTIVATED),
        (_LOW, "IRON_HEPCIDIN", 0.55, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.5, PathwayDirection.SUPPRESSED),
    ],
    "cardiac": [
        (_HIGH, "IL6_JAK_STAT3", 0.55, PathwayDirection.ACTIVATED),
        (_HIGH, "NF_KB", 0.4, PathwayDirection.ACTIVATED),
        (_HIGH, "MITOCHONDRIAL_NAD", 0.35, PathwayDirection.SUPPRESSED),
    ],
    "coagulation": [
        (_HIGH, "NF_KB", 0.5, PathwayDirection.ACTIVATED),
        (_LOW, "NF_KB", 0.35, PathwayDirection.ACTIVATED),
    ],
    "autoimmune": [
        (_HIGH, "AUTOIMMUNE_TARGETING", 0.85, PathwayDirection.ACTIVATED),
        (_HIGH, "NF_KB", 0.5, PathwayDirection.ACTIVATED),
    ],
    "allergy": [
        (_HIGH, "IGE_SENSITIZATION", 0.85, PathwayDirection.ACTIVATED),
        (_HIGH, "NF_KB", 0.35, PathwayDirection.ACTIVATED),
    ],
    "infectious_disease": [
        (_HIGH, "PATHOGEN_BURDEN", 0.8, PathwayDirection.ACTIVATED),
        (_HIGH, "NF_KB", 0.6, PathwayDirection.ACTIVATED),
    ],
    "microbiology": [
        (_HIGH, "PATHOGEN_BURDEN", 0.85, PathwayDirection.ACTIVATED),
    ],
    "celiac_serology": [
        (_HIGH, "FOOD_ANTIGEN_EXPOSURE", 0.9, PathwayDirection.ACTIVATED),
        (_HIGH, "GI_MUCOSAL_BARRIER", 0.5, PathwayDirection.SUPPRESSED),
    ],
    "pharmacogenomics": [
        (_HIGH, "DRUG_METABOLISM_VARIANT", 0.9, PathwayDirection.ACTIVATED),
    ],
    "gi_stool": [
        (_HIGH, "GI_MUCOSAL_BARRIER", 0.6, PathwayDirection.SUPPRESSED),
        (_HIGH, "PATHOGEN_BURDEN", 0.45, PathwayDirection.ACTIVATED),
    ],
    "urinalysis": [
        (_HIGH, "RENAL_FILTRATION", 0.6, PathwayDirection.SUPPRESSED),
        (_HIGH, "PATHOGEN_BURDEN", 0.35, PathwayDirection.ACTIVATED),
    ],
    "tumor_marker": [
        (_HIGH, "NF_KB", 0.45, PathwayDirection.ACTIVATED),
        (_HIGH, "MTOR_AUTOPHAGY", 0.35, PathwayDirection.ACTIVATED),
    ],
    "toxicology": [
        (_HIGH, "NRF2", 0.5, PathwayDirection.SUPPRESSED),
        (_HIGH, "HEPATIC_LIPID", 0.45, PathwayDirection.ACTIVATED),
    ],
    "other": [
        (_HIGH, "NF_KB", 0.3, PathwayDirection.ACTIVATED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.3, PathwayDirection.SUPPRESSED),
    ],
}

# Biomarker-specific rules layered on top of (or instead of) category defaults.
_BIOMARKER_RULES: dict[str, list[tuple[frozenset[LabResultStatus], str, float, PathwayDirection]]] = {
    "RBC": [
        (_LOW, "IRON_HEPCIDIN", 0.75, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.7, PathwayDirection.SUPPRESSED),
    ],
    "Hematocrit": [
        (_LOW, "IRON_HEPCIDIN", 0.7, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.65, PathwayDirection.SUPPRESSED),
    ],
    "MCHC": [
        (_LOW, "IRON_HEPCIDIN", 0.7, PathwayDirection.SUPPRESSED),
        (_HIGH, "ONE_CARBON_METHYLATION", 0.45, PathwayDirection.SUPPRESSED),
    ],
    "Platelet Count": [
        (_LOW, "IRON_HEPCIDIN", 0.4, PathwayDirection.SUPPRESSED),
        (_HIGH, "NF_KB", 0.45, PathwayDirection.ACTIVATED),
        (_LOW, "NF_KB", 0.35, PathwayDirection.ACTIVATED),
    ],
    "MPV": [(_HIGH, "NF_KB", 0.4, PathwayDirection.ACTIVATED)],
    "Haptoglobin": [(_LOW, "IRON_HEPCIDIN", 0.65, PathwayDirection.SUPPRESSED)],
    "Reticulocyte Count": [
        (_HIGH, "IRON_HEPCIDIN", 0.55, PathwayDirection.SUPPRESSED),
        (_HIGH, "ONE_CARBON_METHYLATION", 0.4, PathwayDirection.SUPPRESSED),
    ],
    "Absolute Neutrophils": [
        (_HIGH, "NF_KB", 0.55, PathwayDirection.ACTIVATED),
        (_HIGH, "IL6_JAK_STAT3", 0.45, PathwayDirection.ACTIVATED),
    ],
    "Neutrophils %": [
        (_HIGH, "NF_KB", 0.5, PathwayDirection.ACTIVATED),
        (_HIGH, "IL6_JAK_STAT3", 0.4, PathwayDirection.ACTIVATED),
    ],
    "Absolute Lymphocytes": [(_HIGH, "NF_KB", 0.4, PathwayDirection.ACTIVATED)],
    "Lymphocytes %": [(_HIGH, "NF_KB", 0.35, PathwayDirection.ACTIVATED)],
    "Absolute Monocytes": [(_HIGH, "NF_KB", 0.45, PathwayDirection.ACTIVATED)],
    "Monocytes %": [(_HIGH, "NF_KB", 0.4, PathwayDirection.ACTIVATED)],
    "Absolute Eosinophils": [
        (_HIGH, "IGE_SENSITIZATION", 0.6, PathwayDirection.ACTIVATED),
        (_HIGH, "NF_KB", 0.35, PathwayDirection.ACTIVATED),
    ],
    "Eosinophils %": [
        (_HIGH, "IGE_SENSITIZATION", 0.55, PathwayDirection.ACTIVATED),
    ],
    "Absolute Basophils": [(_HIGH, "IGE_SENSITIZATION", 0.5, PathwayDirection.ACTIVATED)],
    "Basophils %": [(_HIGH, "IGE_SENSITIZATION", 0.45, PathwayDirection.ACTIVATED)],
    "TPO Antibody": [
        (_HIGH, "AUTOIMMUNE_TARGETING", 0.8, PathwayDirection.ACTIVATED),
        (_HIGH, "THYROID_HPT", 0.5, PathwayDirection.SUPPRESSED),
    ],
    "Thyroglobulin Antibody": [
        (_HIGH, "AUTOIMMUNE_TARGETING", 0.75, PathwayDirection.ACTIVATED),
        (_HIGH, "THYROID_HPT", 0.45, PathwayDirection.SUPPRESSED),
    ],
    "Total T3": [
        (_LOW, "THYROID_HPT", 0.7, PathwayDirection.SUPPRESSED),
        (_HIGH, "THYROID_HPT", 0.5, PathwayDirection.ACTIVATED),
    ],
    "Total T4": [
        (_LOW, "THYROID_HPT", 0.7, PathwayDirection.SUPPRESSED),
        (_HIGH, "THYROID_HPT", 0.5, PathwayDirection.ACTIVATED),
    ],
    "Reverse T3": [(_HIGH, "THYROID_HPT", 0.55, PathwayDirection.SUPPRESSED)],
    "Methylmalonic Acid": [
        (_HIGH, "ONE_CARBON_METHYLATION", 0.8, PathwayDirection.SUPPRESSED),
        (_HIGH, "NUTRIENT_DEFICIENCY", 0.85, PathwayDirection.SUPPRESSED),
    ],
    "Homocysteine": [
        (_HIGH, "ONE_CARBON_METHYLATION", 0.9, PathwayDirection.SUPPRESSED),
        (_HIGH, "NF_KB", 0.3, PathwayDirection.ACTIVATED),
    ],
    "Vitamin D": [
        (_LOW, "VITAMIN_D_RECEPTOR", 0.9, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.9, PathwayDirection.SUPPRESSED),
        (_HIGH, "VITAMIN_D_RECEPTOR", 0.5, PathwayDirection.ACTIVATED),
    ],
    "Magnesium": [
        (_LOW, "NUTRIENT_DEFICIENCY", 0.8, PathwayDirection.SUPPRESSED),
        (_LOW, "INSULIN_PI3K_AKT", 0.35, PathwayDirection.SUPPRESSED),
    ],
    "Zinc": [
        (_LOW, "NUTRIENT_DEFICIENCY", 0.8, PathwayDirection.SUPPRESSED),
        (_LOW, "ONE_CARBON_METHYLATION", 0.3, PathwayDirection.SUPPRESSED),
    ],
    "Copper": [
        (_LOW, "NUTRIENT_DEFICIENCY", 0.8, PathwayDirection.SUPPRESSED),
    ],
    "Selenium": [
        (_LOW, "NUTRIENT_DEFICIENCY", 0.75, PathwayDirection.SUPPRESSED),
    ],
    "Iron": [
        (_LOW, "IRON_HEPCIDIN", 0.8, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.85, PathwayDirection.SUPPRESSED),
    ],
    "B12": [
        (_LOW, "ONE_CARBON_METHYLATION", 0.8, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.9, PathwayDirection.SUPPRESSED),
    ],
    "Folate": [
        (_LOW, "ONE_CARBON_METHYLATION", 0.85, PathwayDirection.SUPPRESSED),
        (_LOW, "NUTRIENT_DEFICIENCY", 0.9, PathwayDirection.SUPPRESSED),
    ],
    "MCV": [
        (_HIGH, "ONE_CARBON_METHYLATION", 0.85, PathwayDirection.SUPPRESSED),
        (_HIGH, "NUTRIENT_DEFICIENCY", 0.85, PathwayDirection.SUPPRESSED),
        (_HIGH, "THYROID_HPT", 0.35, PathwayDirection.SUPPRESSED),
        (_LOW, "IRON_HEPCIDIN", 0.8, PathwayDirection.SUPPRESSED),
    ],
    "MCH": [
        (_HIGH, "ONE_CARBON_METHYLATION", 0.8, PathwayDirection.SUPPRESSED),
        (_HIGH, "NUTRIENT_DEFICIENCY", 0.8, PathwayDirection.SUPPRESSED),
        (_LOW, "IRON_HEPCIDIN", 0.75, PathwayDirection.SUPPRESSED),
    ],
    "RDW": [
        (_HIGH, "IRON_HEPCIDIN", 0.7, PathwayDirection.SUPPRESSED),
        (_HIGH, "ONE_CARBON_METHYLATION", 0.6, PathwayDirection.SUPPRESSED),
        (_HIGH, "NUTRIENT_DEFICIENCY", 0.75, PathwayDirection.SUPPRESSED),
    ],
    "Fecal Lactoferrin": [
        (_HIGH, "PATHOGEN_BURDEN", 0.75, PathwayDirection.ACTIVATED),
        (_HIGH, "GI_MUCOSAL_BARRIER", 0.65, PathwayDirection.SUPPRESSED),
        (_HIGH, "BIOFILM_ADHESION", 0.55, PathwayDirection.ACTIVATED),
    ],
}

_QUALITATIVE_KINDS = frozenset({"qualitative", "culture", "genotype"})


def _rules_for_biomarker(name: str, ref: dict) -> list[tuple[frozenset[LabResultStatus], str, float, PathwayDirection]]:
    if name in _BIOMARKER_RULES:
        return _BIOMARKER_RULES[name]
    category = ref.get("category", "other")
    if ref.get("result_kind") in _QUALITATIVE_KINDS:
        return _CATEGORY_RULES.get(category, _CATEGORY_RULES["other"])
    return _CATEGORY_RULES.get(category, _CATEGORY_RULES["other"])


def build_catalog_pathway_configs(
    *,
    skip_biomarkers: set[str] | None = None,
) -> list[tuple[str, set[LabResultStatus], str, float, PathwayDirection]]:
    """Expand category/biomarker templates into pathway_mapper rule tuples."""
    skip = skip_biomarkers or set()
    configs: list[tuple[str, set[LabResultStatus], str, float, PathwayDirection]] = []
    for name, ref in REFERENCE_DATA.items():
        if name in skip:
            continue
        for statuses, pathway_code, weight, direction in _rules_for_biomarker(name, ref):
            configs.append((name, set(statuses), pathway_code, weight, direction))
    return configs


def catalog_biomarkers_without_pathways(
    explicit_biomarkers: set[str],
) -> list[str]:
    """Catalog biomarkers that would have zero rules if only explicit configs existed."""
    covered = set(explicit_biomarkers)
    for name in REFERENCE_DATA:
        if name not in covered and _rules_for_biomarker(name, REFERENCE_DATA[name]):
            covered.add(name)
    return sorted(set(REFERENCE_DATA.keys()) - explicit_biomarkers)