"""Medication-aware lab interpretation context.

Surfaces how current medications may influence or confound lab results and
recommended interventions — deterministic, not LLM-generated.
"""

from __future__ import annotations

import re

from app.schemas.pipeline import NormalizedLabResult

_MEDICATION_RULES: list[dict] = [
    {
        "pattern": re.compile(r"warfarin|coumadin|jantoven", re.I),
        "medication_class": "anticoagulant",
        "lab_notes": [
            "Warfarin therapy directly affects PT/INR — interpret coagulation markers in that context.",
            "Several botanicals (garlic, ginkgo, turmeric/curcumin) may potentiate anticoagulant effect.",
        ],
        "relevant_biomarkers": {"PT", "INR", "PTT"},
    },
    {
        "pattern": re.compile(r"metformin|glucophage", re.I),
        "medication_class": "antidiabetic",
        "lab_notes": [
            "Long-term metformin use is associated with lower B12 in some patients — consider B12 status.",
            "Glucose and HbA1c should be interpreted alongside active metformin therapy.",
        ],
        "relevant_biomarkers": {"Glucose", "HbA1c", "B12", "Insulin"},
    },
    {
        "pattern": re.compile(r"statin|atorvastatin|rosuvastatin|simvastatin|pravastatin|lovastatin", re.I),
        "medication_class": "statin",
        "lab_notes": [
            "Statin therapy commonly lowers LDL — abnormal lipid flags may reflect inadequate control vs. medication effect.",
            "Statin-associated myopathy risk may correlate with CK; CoQ10 depletion is a known consideration.",
        ],
        "relevant_biomarkers": {"LDL", "Total Cholesterol", "ApoB", "CK", "ALT", "AST"},
    },
    {
        "pattern": re.compile(r"levothyroxine|synthroid|tirosint|armour thyroid|np thyroid", re.I),
        "medication_class": "thyroid_replacement",
        "lab_notes": [
            "TSH and free T4 should be interpreted in the context of thyroid hormone replacement dosing.",
        ],
        "relevant_biomarkers": {"TSH", "Free T4", "Free T3", "Total T4"},
    },
    {
        "pattern": re.compile(r"prednisone|prednisolone|methylprednisolone|dexamethasone|cortisone", re.I),
        "medication_class": "corticosteroid",
        "lab_notes": [
            "Corticosteroids can elevate glucose, WBC, and suppress adrenal axis markers.",
            "Inflammatory markers (CRP, ESR) may be blunted during steroid therapy.",
        ],
        "relevant_biomarkers": {"Glucose", "WBC", "CRP", "ESR", "Cortisol"},
    },
    {
        "pattern": re.compile(r"lisinopril|enalapril|ramipril|benazepril|losartan|valsartan|olmesartan", re.I),
        "medication_class": "ace_arb",
        "lab_notes": [
            "ACE inhibitors/ARBs can affect potassium and creatinine — monitor renal/electrolyte panels.",
        ],
        "relevant_biomarkers": {"Potassium", "Creatinine", "eGFR", "BUN"},
    },
    {
        "pattern": re.compile(r"omeprazole|pantoprazole|esomeprazole|lansoprazole|rabeprazole|ppi", re.I),
        "medication_class": "ppi",
        "lab_notes": [
            "PPI use may lower B12 and magnesium over time; can affect iron absorption.",
            "H. pylori testing should be interpreted knowing recent PPI use can cause false negatives.",
        ],
        "relevant_biomarkers": {"B12", "Magnesium", "Ferritin", "Iron", "H. pylori Urea Breath Test", "H. pylori Stool Antigen"},
    },
    {
        "pattern": re.compile(r"methotrexate|azathioprine|cyclosporine|tacrolimus|mycophenolate", re.I),
        "medication_class": "immunosuppressant",
        "lab_notes": [
            "Immunosuppressant therapy may elevate liver enzymes and affect CBC differentials.",
            "Immune-stimulating botanicals may be inappropriate without specialist guidance.",
        ],
        "relevant_biomarkers": {"ALT", "AST", "WBC", "Platelet Count", "Creatinine"},
    },
    {
        "pattern": re.compile(r"insulin|lantus|levemir|humalog|novolog|ozempic|wegovy|semaglutide|mounjaro|tirzepatide", re.I),
        "medication_class": "insulin_incretin",
        "lab_notes": [
            "Glucose, HbA1c, and insulin values should be interpreted alongside active glucose-lowering therapy.",
        ],
        "relevant_biomarkers": {"Glucose", "HbA1c", "Insulin", "C-Peptide"},
    },
]

_NO_GROWTH = frozenset({"no growth", "not isolated", "negative", "none", "sterile"})


def _matched_rules(medications: list[str]) -> list[dict]:
    if not medications:
        return []
    blob = " ".join(medications)
    return [rule for rule in _MEDICATION_RULES if rule["pattern"].search(blob)]


def build_medication_context(
    normalized_labs: list[NormalizedLabResult],
    health_profile: dict,
) -> dict:
    """Build medication-aware interpretation notes for the report."""
    medications = health_profile.get("current_medications") or []
    supplements = health_profile.get("current_supplements") or []
    rules = _matched_rules(medications)

    if not rules and not medications:
        return {
            "has_medications": False,
            "medications": [],
            "supplements": supplements,
            "notes": [],
            "biomarker_specific_notes": [],
        }

    measured = {lab.biomarker_name for lab in normalized_labs}
    notes: list[str] = []
    biomarker_notes: list[dict] = []

    for rule in rules:
        for note in rule["lab_notes"]:
            if note not in notes:
                notes.append(note)
        for biomarker in rule["relevant_biomarkers"]:
            if biomarker in measured:
                biomarker_notes.append(
                    {
                        "biomarker_name": biomarker,
                        "medication_class": rule["medication_class"],
                        "note": rule["lab_notes"][0],
                    }
                )

    return {
        "has_medications": bool(medications),
        "medications": medications,
        "supplements": supplements,
        "notes": notes,
        "biomarker_specific_notes": biomarker_notes,
    }