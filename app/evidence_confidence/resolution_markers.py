"""Confirmatory biomarkers that resolve an intervention or pathway.

Used by data-sufficiency scoring. These are *resolution* markers, not a
diagnosis panel. Presence of a listed marker (any common alias) counts as
assessed; absence is a named gap.
"""

from __future__ import annotations

# pathway_code -> markers that would resolve that branch
PATHWAY_RESOLUTION_MARKERS: dict[str, tuple[str, ...]] = {
    "NF_KB": ("CRP", "hs-CRP", "ESR"),
    "IL6_JAK_STAT3": ("CRP", "hs-CRP", "IL-6"),
    "INSULIN_PI3K_AKT": ("Glucose", "Insulin", "HbA1c"),
    "GLP1_INCRETINS": ("Glucose", "Insulin", "HbA1c"),
    "THYROID_HPT": ("TSH", "Free T4", "Free T3"),
    "NUTRIENT_DEFICIENCY": ("Vitamin B12", "Folate", "Vitamin D", "Ferritin"),
    "ONE_CARBON_METHYLATION": ("Vitamin B12", "Folate", "Homocysteine", "MMA"),
    "IRON_HEPCIDIN": ("Ferritin", "Iron", "TIBC", "Transferrin Saturation", "Hemoglobin"),
    "HEPATIC_LIPID": ("LDL", "HDL", "Triglycerides", "ALT", "AST"),
    "RENAL_FILTRATION": ("Creatinine", "eGFR"),
    "HPA_AXIS": ("Cortisol", "DHEA-S"),
    "MTOR_AUTOPHAGY": ("Insulin", "Glucose", "HbA1c"),
    "PURINE_URIC_ACID": ("Uric Acid",),
    "NRF2": ("GGT", "ALT", "Bilirubin"),
    "AMPK": ("Glucose", "Insulin", "HbA1c"),
}

# intervention name (canonical or common catalog name) -> confirmatory set
INTERVENTION_RESOLUTION_MARKERS: dict[str, tuple[str, ...]] = {
    "Vitamin B12": ("Vitamin B12", "MMA", "Homocysteine", "MCV", "Folate"),
    "Methylcobalamin": ("Vitamin B12", "MMA", "Homocysteine", "MCV", "Folate"),
    "Cyanocobalamin": ("Vitamin B12", "MMA", "Homocysteine", "MCV", "Folate"),
    "Folate": ("Folate", "Vitamin B12", "Homocysteine", "MCV"),
    "Methylfolate": ("Folate", "Vitamin B12", "Homocysteine", "MCV"),
    "Iron": ("Ferritin", "Iron", "TIBC", "Transferrin Saturation", "Hemoglobin"),
    "Ferrous Bisglycinate": ("Ferritin", "Iron", "TIBC", "Hemoglobin"),
    "Vitamin D": ("Vitamin D", "Calcium", "PTH"),
    "Vitamin D3": ("Vitamin D", "Calcium", "PTH"),
    "Berberine": ("Glucose", "Insulin", "HbA1c", "LDL"),
    "Omega-3": ("Triglycerides", "LDL", "HDL", "hs-CRP", "CRP"),
    "Curcumin": ("CRP", "hs-CRP", "ESR"),
    "Quercetin": ("Uric Acid", "CRP"),
    "Selenium": ("TSH", "Free T4", "Selenium"),
    "Ashwagandha": ("TSH", "Free T4", "Cortisol"),
    "NAC": ("GGT", "ALT", "GSH"),
}

# Alias groups: any member satisfies any other member in the same group.
_ALIAS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"crp", "hscrp", "c reactive protein", "high sensitivity crp"}),
    frozenset({"vitamin b12", "b12", "cobalamin", "methylcobalamin", "cyanocobalamin"}),
    frozenset({"folate", "folic acid", "methylfolate", "vitamin b9"}),
    frozenset({"mma", "methylmalonic acid"}),
    frozenset({"homocysteine", "hcy"}),
    frozenset({"hba1c", "hemoglobin a1c", "a1c", "glycohemoglobin"}),
    frozenset({"vitamin d", "vitamin d3", "25 oh vitamin d", "25 hydroxy vitamin d"}),
    frozenset({"egfr", "estimated gfr", "gfr"}),
    frozenset({"ldl", "ldl c", "ldl cholesterol"}),
    frozenset({"hdl", "hdl c", "hdl cholesterol"}),
    frozenset({"mcv", "mean cell volume", "mean corpuscular volume"}),
)


def normalize_marker_name(name: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in name).split())


def _alias_set(name: str) -> set[str]:
    key = normalize_marker_name(name)
    aliases = {key}
    for group in _ALIAS_GROUPS:
        if key in group:
            aliases.update(group)
    return aliases


def present_marker_keys(lab_names: list[str]) -> set[str]:
    keys: set[str] = set()
    for name in lab_names:
        keys.update(_alias_set(name))
    return keys


def marker_is_present(marker: str, present_keys: set[str]) -> bool:
    return bool(_alias_set(marker) & present_keys)


def resolution_markers_for(intervention_name: str, pathway_codes: set[str]) -> list[str]:
    """Ordered unique confirmatory markers for this recommendation."""
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(names: tuple[str, ...] | list[str]) -> None:
        for name in names:
            key = normalize_marker_name(name)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(name)

    _add(INTERVENTION_RESOLUTION_MARKERS.get(intervention_name, ()))
    for code in sorted(pathway_codes):
        _add(PATHWAY_RESOLUTION_MARKERS.get(code, ()))
    return ordered
