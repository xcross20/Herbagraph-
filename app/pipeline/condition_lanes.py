"""Condition-aligned report lanes — separate from lab-driven clinical priorities.

Documented conditions (hypertension, diabetes, …) produce a dedicated
``condition_aligned`` insights block. Items never alter clinical_priority_score.
"""

from __future__ import annotations

from app.safety_engine.condition_catalog import CONDITION_CATALOG, active_conditions

MODEL = "condition_lanes_v1"

_DISCLAIMER = (
    "Condition-aligned considerations are based on documented patient context, "
    "not on lab abnormality ranking. They do not replace clinical judgment, "
    "blood-pressure measurement, or a treatment plan from a licensed clinician."
)

# Curated playbooks only — not a full PubMed dump.
# kind: lifestyle | safety_caution | medication_review | monitoring | nutrition
CONDITION_PLAYBOOKS: dict[str, dict] = {
    "hypertension": {
        "label": "Hypertension",
        "related_biomarkers": [
            "Creatinine",
            "eGFR",
            "Potassium",
            "Sodium",
            "BUN",
            "LDL",
            "LDL Cholesterol",
            "HDL",
            "HDL Cholesterol",
            "Triglycerides",
            "Total Cholesterol",
            "ApoB",
            "hs-CRP",
            "CRP",
            "Glucose",
            "HbA1c",
        ],
        "considerations": [
            {
                "title": "DASH-style dietary pattern",
                "kind": "lifestyle",
                "rationale": (
                    "Dietary Approaches to Stop Hypertension (DASH) patterns — higher produce, "
                    "lower sodium, adequate potassium from food — are first-line lifestyle support "
                    "for elevated blood pressure when appropriate for the patient."
                ),
            },
            {
                "title": "Sodium awareness and potassium-rich foods (if kidney function allows)",
                "kind": "nutrition",
                "rationale": (
                    "Limiting excess sodium and emphasizing potassium-rich whole foods can support "
                    "BP control. Confirm kidney function and potassium status before aggressive "
                    "potassium-focused advice."
                ),
            },
            {
                "title": "Avoid glycyrrhizin-containing licorice products",
                "kind": "safety_caution",
                "rationale": (
                    "Glycyrrhizin can cause sodium retention, potassium loss, and elevated blood "
                    "pressure. Prefer deglycyrrhizinated (DGL) forms only if a clinician agrees."
                ),
            },
            {
                "title": "Review BP medications for herb and supplement interactions",
                "kind": "medication_review",
                "rationale": (
                    "ACE inhibitors, ARBs, diuretics, calcium-channel blockers, and beta-blockers "
                    "can interact with herbs, electrolytes, and some supplements. Align any new "
                    "botanical with the current regimen."
                ),
            },
            {
                "title": "Home BP monitoring context",
                "kind": "monitoring",
                "rationale": (
                    "This lab report does not measure blood pressure. Condition-aligned items "
                    "assume documented hypertension; titration and urgency depend on measured BP."
                ),
            },
        ],
    },
    "diabetes": {
        "label": "Diabetes",
        "related_biomarkers": [
            "Glucose",
            "HbA1c",
            "Insulin",
            "Fasting Insulin",
            "Triglycerides",
            "HDL",
            "HDL Cholesterol",
            "LDL",
            "LDL Cholesterol",
            "Creatinine",
            "eGFR",
            "Urine Microalbumin",
            "Albumin/Creatinine Ratio",
        ],
        "considerations": [
            {
                "title": "Glycemic pattern review on this panel",
                "kind": "monitoring",
                "rationale": (
                    "When glucose or HbA1c is on the panel, interpret in the context of known "
                    "diabetes rather than as a new diagnosis. Missing HbA1c or insulin limits "
                    "chronicity assessment."
                ),
            },
            {
                "title": "Carbohydrate quality and fiber-forward pattern",
                "kind": "lifestyle",
                "rationale": (
                    "Emphasizing fiber, non-starchy vegetables, and reduced ultra-processed "
                    "carbohydrates is a standard supportive pattern alongside prescribed therapy."
                ),
            },
            {
                "title": "Coordinate supplements with diabetes medications",
                "kind": "medication_review",
                "rationale": (
                    "Agents that affect glucose (e.g. berberine, high-dose chromium, some herbals) "
                    "may potentiate hypoglycemia with insulin or sulfonylureas. Clinician review first."
                ),
            },
            {
                "title": "Cardiometabolic and kidney co-monitoring",
                "kind": "monitoring",
                "rationale": (
                    "Diabetes care commonly includes lipids, kidney function, and urine albumin. "
                    "Gaps on this panel are diagnostic opportunities, not proof of absence of risk."
                ),
            },
        ],
    },
    "kidney_disease": {
        "label": "Kidney disease",
        "related_biomarkers": [
            "Creatinine",
            "eGFR",
            "BUN",
            "Potassium",
            "Sodium",
            "Phosphorus",
            "Calcium",
            "Albumin",
            "Urine Microalbumin",
            "Albumin/Creatinine Ratio",
            "Cystatin C",
        ],
        "considerations": [
            {
                "title": "Dose and mineral caution for supplements",
                "kind": "safety_caution",
                "rationale": (
                    "Reduced GFR changes clearance of magnesium, potassium, fat-soluble vitamins, "
                    "and many botanicals. Prefer kidney-safe dosing only under clinician guidance."
                ),
            },
            {
                "title": "Avoid high-protein crash diets and NSAID-heavy self-care without advice",
                "kind": "lifestyle",
                "rationale": (
                    "Protein load and nephrotoxic OTC patterns can stress residual kidney function. "
                    "Align diet and pain-relief choices with nephrology guidance."
                ),
            },
            {
                "title": "Electrolyte-aware nutrition",
                "kind": "nutrition",
                "rationale": (
                    "Potassium, phosphorus, and sodium targets depend on stage and labs. "
                    "Generic 'high potassium for BP' advice may be inappropriate in advanced CKD."
                ),
            },
            {
                "title": "Review renally cleared medications and contrast/procedure plans",
                "kind": "medication_review",
                "rationale": (
                    "Documented kidney disease should prompt medication reconciliation and "
                    "procedure planning with the care team — outside automated lab prioritization."
                ),
            },
        ],
    },
    "pregnancy": {
        "label": "Pregnancy",
        "related_biomarkers": [
            "Hemoglobin",
            "Hematocrit",
            "Ferritin",
            "Iron",
            "TSH",
            "Free T4",
            "Glucose",
            "Vitamin D, 25-OH",
            "Folate",
            "Vitamin B12",
        ],
        "considerations": [
            {
                "title": "Many herbs and high-dose supplements are not pregnancy-validated",
                "kind": "safety_caution",
                "rationale": (
                    "Pregnancy is a hard safety context: avoid non-essential botanicals, peptides, "
                    "and high-dose fat-soluble vitamins unless prescribed. Prefer obstetric guidance."
                ),
            },
            {
                "title": "Prioritize obstetric-approved nutrition (folate, iron as indicated)",
                "kind": "nutrition",
                "rationale": (
                    "Prenatal folate/folic acid, iron when deficient, and vitamin D per obstetric "
                    "standards dominate over experimental nutraceuticals."
                ),
            },
            {
                "title": "Lab interpretation is trimester-dependent",
                "kind": "monitoring",
                "rationale": (
                    "Reference ranges and urgency for hemoglobin, thyroid, and glucose shift in "
                    "pregnancy. Use obstetric reference ranges when available."
                ),
            },
        ],
    },
    "thyroid_disease": {
        "label": "Thyroid disease",
        "related_biomarkers": [
            "TSH",
            "Free T4",
            "Free T3",
            "TPO Antibodies",
            "Thyroglobulin Antibodies",
            "Reverse T3",
        ],
        "considerations": [
            {
                "title": "Time supplements away from thyroid hormone if prescribed",
                "kind": "medication_review",
                "rationale": (
                    "Calcium, iron, and some fibers can reduce levothyroxine absorption. Separate "
                    "dosing windows matter more than adding new thyroid 'boosters'."
                ),
            },
            {
                "title": "Iodine and high-dose selenium need context",
                "kind": "safety_caution",
                "rationale": (
                    "Excess iodine can worsen some thyroid disorders; selenium is not universally "
                    "indicated. Base changes on full thyroid labs and clinician input."
                ),
            },
            {
                "title": "Prefer full thyroid panel when history is known",
                "kind": "monitoring",
                "rationale": (
                    "With known thyroid disease, TSH alone is often insufficient. Free T4/T3 and "
                    "antibodies clarify control and autoimmune activity."
                ),
            },
        ],
    },
    "liver_disease": {
        "label": "Liver disease",
        "related_biomarkers": [
            "ALT",
            "AST",
            "GGT",
            "Alkaline Phosphatase",
            "Bilirubin, Total",
            "Albumin",
            "Platelet Count",
        ],
        "considerations": [
            {
                "title": "Minimize hepatically metabolized herbs and alcohol",
                "kind": "safety_caution",
                "rationale": (
                    "Many multi-ingredient herbals and concentrated extracts carry liver risk. "
                    "With known liver disease, default to fewer non-essential products."
                ),
            },
            {
                "title": "Medication and supplement reconciliation",
                "kind": "medication_review",
                "rationale": (
                    "Acetaminophen load, certain antifungals, and herbals should be reviewed when "
                    "liver enzymes or known hepatic disease are present."
                ),
            },
        ],
    },
}


def _measured_biomarker_names(biomarker_summary: dict | None) -> set[str]:
    if not biomarker_summary:
        return set()
    names: set[str] = set()
    for m in biomarker_summary.get("measured_biomarkers") or []:
        name = m.get("biomarker_name")
        if name:
            names.add(str(name))
    return names


def _abnormal_biomarker_names(biomarker_summary: dict | None) -> set[str]:
    if not biomarker_summary:
        return set()
    abnormal = {"critical_low", "low", "high", "critical_high"}
    names: set[str] = set()
    for m in biomarker_summary.get("measured_biomarkers") or []:
        if m.get("status") in abnormal and m.get("biomarker_name"):
            names.add(str(m["biomarker_name"]))
    return names


def _lab_overlap(related: list[str], measured: set[str], abnormal: set[str]) -> list[dict]:
    """Return related biomarkers present on this panel, abnormal ones first."""
    rows: list[dict] = []
    for name in related:
        if name not in measured:
            continue
        rows.append(
            {
                "biomarker_name": name,
                "on_panel": True,
                "abnormal": name in abnormal,
            }
        )
    rows.sort(key=lambda r: (not r["abnormal"], r["biomarker_name"]))
    return rows


def _medication_hints(medications: list[str] | None) -> list[str]:
    if not medications:
        return []
    return [str(m).strip() for m in medications if str(m).strip()][:12]


def build_condition_aligned(
    health_profile: dict | None = None,
    biomarker_summary: dict | None = None,
    *,
    known_conditions: list[str] | None = None,
    current_medications: list[str] | None = None,
) -> dict:
    """Build condition-aligned considerations lane (never mutates lab priority scores)."""
    profile = health_profile or {}
    conditions_raw = list(known_conditions if known_conditions is not None else (profile.get("known_conditions") or []))
    medications = list(
        current_medications
        if current_medications is not None
        else (profile.get("current_medications") or [])
    )
    # Also allow patient_context merge shape
    if not conditions_raw and profile.get("patient_context"):
        conditions_raw = list((profile.get("patient_context") or {}).get("known_conditions") or [])

    active = active_conditions([str(c) for c in conditions_raw])
    measured = _measured_biomarker_names(biomarker_summary)
    abnormal = _abnormal_biomarker_names(biomarker_summary)
    meds = _medication_hints(medications)

    items: list[dict] = []
    # Stable order: follow CONDITION_CATALOG declaration order
    for key in CONDITION_CATALOG:
        if key not in active:
            continue
        playbook = CONDITION_PLAYBOOKS.get(key)
        if not playbook:
            # Matched catalog condition without a playbook — still surface a minimal card
            meta = CONDITION_CATALOG[key]
            items.append(
                {
                    "condition_key": key,
                    "label": meta.get("label") or key.replace("_", " ").title(),
                    "source": "known_conditions",
                    "considerations": [
                        {
                            "title": "Documented condition on profile",
                            "kind": "monitoring",
                            "rationale": (
                                f"{meta.get('label', key)} is recorded on the patient profile. "
                                "No curated condition playbook is defined yet; safety engine "
                                "rules may still apply to individual interventions."
                            ),
                        }
                    ],
                    "lab_overlap": [],
                    "medications_noted": meds,
                    "disclaimer": _DISCLAIMER,
                }
            )
            continue

        considerations: list[dict] = []
        has_med_review = False
        for raw in playbook["considerations"]:
            c = dict(raw)
            if c.get("kind") == "medication_review":
                has_med_review = True
                if meds:
                    c["related_medications"] = meds
            considerations.append(c)

        overlap = _lab_overlap(list(playbook.get("related_biomarkers") or []), measured, abnormal)
        items.append(
            {
                "condition_key": key,
                "label": playbook.get("label") or CONDITION_CATALOG[key].get("label") or key,
                "source": "known_conditions",
                "considerations": considerations,
                "lab_overlap": overlap,
                "lab_overlap_note": (
                    "Related biomarkers on this panel are listed for context only; "
                    "they do not raise condition-lane items into lab-driven priorities."
                    if overlap
                    else "No strongly related biomarkers from this condition's watchlist were measured on this panel."
                ),
                "medications_noted": meds if has_med_review else [],
                "disclaimer": _DISCLAIMER,
            }
        )

    unmapped = []
    if conditions_raw and not items:
        # Free-text that did not match catalog
        unmapped = [str(c) for c in conditions_raw if str(c).strip()]
    elif conditions_raw:
        # Conditions listed but not catalog-matched
        for raw in conditions_raw:
            raw_s = str(raw).strip()
            if not raw_s:
                continue
            if not active_conditions([raw_s]):
                unmapped.append(raw_s)

    return {
        "model": MODEL,
        "items": items,
        "unmapped_conditions": unmapped[:10],
        "section_title": "Condition-aligned considerations",
        "section_subtitle": (
            "Based on documented conditions — not ranked by lab abnormality. "
            "Separate from Clinical Priorities above."
        ),
        "disclaimer": _DISCLAIMER,
        "empty": len(items) == 0,
    }
