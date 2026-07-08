"""MVP medication catalog (~40 common outpatient drugs) with alias tokens for matching."""

from __future__ import annotations

# name -> {aliases, drug_class}
MEDICATION_CATALOG: dict[str, dict] = {
    "Warfarin": {"aliases": ["coumadin", "jantoven"], "drug_class": "anticoagulant"},
    "Apixaban": {"aliases": ["eliquis"], "drug_class": "anticoagulant"},
    "Rivaroxaban": {"aliases": ["xarelto"], "drug_class": "anticoagulant"},
    "Dabigatran": {"aliases": ["pradaxa"], "drug_class": "anticoagulant"},
    "Aspirin": {"aliases": ["asa", "acetylsalicylic acid"], "drug_class": "antiplatelet"},
    "Clopidogrel": {"aliases": ["plavix"], "drug_class": "antiplatelet"},
    "Metformin": {"aliases": ["glucophage"], "drug_class": "antidiabetic"},
    "Insulin": {"aliases": ["insulin glargine", "insulin lispro", "lantus", "humalog", "novolog"], "drug_class": "antidiabetic"},
    "Glipizide": {"aliases": ["glucotrol"], "drug_class": "antidiabetic"},
    "Sitagliptin": {"aliases": ["januvia"], "drug_class": "dpp4_inhibitor"},
    "Semaglutide": {"aliases": ["ozempic", "wegovy", "rybelsus"], "drug_class": "glp1_agonist"},
    "Levothyroxine": {"aliases": ["synthroid", "levoxyl", "tirosint"], "drug_class": "thyroid"},
    "Methimazole": {"aliases": ["tapazole"], "drug_class": "thyroid"},
    "Atorvastatin": {"aliases": ["lipitor"], "drug_class": "statin"},
    "Rosuvastatin": {"aliases": ["crestor"], "drug_class": "statin"},
    "Simvastatin": {"aliases": ["zocor"], "drug_class": "statin"},
    "Lisinopril": {"aliases": [], "drug_class": "ace_inhibitor"},
    "Losartan": {"aliases": ["cozaar"], "drug_class": "arb"},
    "Amlodipine": {"aliases": ["norvasc"], "drug_class": "ccb"},
    "Metoprolol": {"aliases": ["lopressor", "toprol"], "drug_class": "beta_blocker"},
    "Hydrochlorothiazide": {"aliases": ["hctz", "microzide"], "drug_class": "diuretic"},
    "Furosemide": {"aliases": ["lasix"], "drug_class": "diuretic"},
    "Sertraline": {"aliases": ["zoloft"], "drug_class": "ssri"},
    "Escitalopram": {"aliases": ["lexapro"], "drug_class": "ssri"},
    "Fluoxetine": {"aliases": ["prozac"], "drug_class": "ssri"},
    "Venlafaxine": {"aliases": ["effexor"], "drug_class": "snri"},
    "Bupropion": {"aliases": ["wellbutrin"], "drug_class": "ndri"},
    "Omeprazole": {"aliases": ["prilosec"], "drug_class": "ppi"},
    "Pantoprazole": {"aliases": ["protonix"], "drug_class": "ppi"},
    "Cyclosporine": {"aliases": ["neoral", "sandimmune"], "drug_class": "immunosuppressant"},
    "Tacrolimus": {"aliases": ["prograf"], "drug_class": "immunosuppressant"},
    "Methotrexate": {"aliases": ["trexall"], "drug_class": "immunosuppressant"},
    "Prednisone": {"aliases": ["deltasone"], "drug_class": "corticosteroid"},
    "Amiodarone": {"aliases": ["pacerone"], "drug_class": "antiarrhythmic"},
    "Digoxin": {"aliases": ["lanoxin"], "drug_class": "cardiac_glycoside"},
    "Phenytoin": {"aliases": ["dilantin"], "drug_class": "anticonvulsant"},
    "Carbamazepine": {"aliases": ["tegretol"], "drug_class": "anticonvulsant"},
    "Lithium": {"aliases": [], "drug_class": "mood_stabilizer"},
    "Alendronate": {"aliases": ["fosamax"], "drug_class": "bisphosphonate"},
    "Allopurinol": {"aliases": ["zyloprim"], "drug_class": "uric_acid_lowering"},
    "Colchicine": {"aliases": [], "drug_class": "anti_inflammatory"},
    "Acetaminophen": {"aliases": ["tylenol", "paracetamol"], "drug_class": "analgesic"},
    "Ibuprofen": {"aliases": ["advil", "motrin"], "drug_class": "nsaid"},
    "Gabapentin": {"aliases": ["neurontin"], "drug_class": "neurologic"},
    "Tramadol": {"aliases": ["ultram"], "drug_class": "analgesic"},
}


def medication_aliases() -> dict[str, str]:
    """Map lowercase alias token -> canonical medication name."""
    mapping: dict[str, str] = {}
    for name, meta in MEDICATION_CATALOG.items():
        mapping[name.lower()] = name
        for alias in meta.get("aliases", []):
            mapping[alias.lower()] = name
    return mapping


def resolve_medication(medication_text: str) -> str | None:
    """Best-effort match of free-text medication line to catalog name."""
    import re

    text = medication_text.lower()
    aliases = medication_aliases()
    # Longest alias first to avoid partial false positives.
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return aliases[alias]
    return None


def matched_patient_medications(medications: list[str]) -> list[str]:
    """Return canonical medication names detected in patient medication list."""
    found: list[str] = []
    seen: set[str] = set()
    for med in medications:
        resolved = resolve_medication(med)
        if resolved and resolved not in seen:
            seen.add(resolved)
            found.append(resolved)
    return found