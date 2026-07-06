"""Stage 6: Safety Layer.

Checks every LLM-generated recommendation against a drug-herb interaction
database, a contraindication database, and a regulated/emerging-intervention
list. Contraindicated recommendations are removed from the final report.
"""

import re

from app.models.enums import SafetyRiskLevel
from app.schemas.pipeline import LLMRecommendation, SafetyReport, ScoredRecommendation

# intervention name (lowercase) -> list of {"drug_name", "severity", "mechanism", "note"}
_DRUG_HERB_INTERACTIONS: dict[str, list[dict]] = {
    "boswellia serrata": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "May potentiate anticoagulant effect.", "note": "Monitor INR."},
    ],
    "curcumin": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Antiplatelet activity may potentiate anticoagulant effect.", "note": None},
        {"drug_name": "Chemotherapy", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "May interact with oxidative mechanisms of certain chemotherapeutics.",
         "note": "Discuss with oncologist."},
    ],
    "berberine": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "May potentiate anticoagulant effect.", "note": None},
        {"drug_name": "Metformin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
        {"drug_name": "Cyclosporine", "severity": SafetyRiskLevel.HIGH,
         "mechanism": "Inhibits CYP3A4/P-glycoprotein, raising cyclosporine levels.", "note": None},
        {"drug_name": "Insulin/antidiabetics", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
    ],
    "omega-3": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive antiplatelet/anticoagulant effect at high doses.", "note": None},
    ],
    "coq10": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.LOW,
         "mechanism": "Structural similarity to vitamin K may mildly reduce anticoagulant effect.", "note": None},
    ],
    "st. john's wort": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.HIGH,
         "mechanism": "Induces CYP450 enzymes, reducing anticoagulant efficacy.", "note": None},
        {"drug_name": "SSRIs/SNRIs", "severity": SafetyRiskLevel.HIGH,
         "mechanism": "Additive serotonergic effect; risk of serotonin syndrome.", "note": None},
        {"drug_name": "Cyclosporine", "severity": SafetyRiskLevel.HIGH,
         "mechanism": "Induces CYP3A4, lowering cyclosporine levels.", "note": None},
    ],
    "ginkgo": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive antiplatelet effect.", "note": None},
    ],
    "ashwagandha": [
        {"drug_name": "Levothyroxine", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "May increase thyroid hormone levels.", "note": "Monitor TSH."},
        {"drug_name": "Immunosuppressants", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Immune-stimulating effect may counteract immunosuppressive therapy.", "note": None},
    ],
    "alpha lipoic acid": [
        {"drug_name": "Levothyroxine", "severity": SafetyRiskLevel.LOW,
         "mechanism": "May reduce thyroid hormone absorption if taken simultaneously.", "note": None},
        {"drug_name": "Insulin/antidiabetics", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
    ],
    "chromium": [
        {"drug_name": "Insulin/antidiabetics", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
    ],
    "milk thistle": [
        {"drug_name": "Statins", "severity": SafetyRiskLevel.LOW,
         "mechanism": "May mildly inhibit CYP-mediated statin metabolism.", "note": None},
    ],
    "quercetin": [
        {"drug_name": "Chemotherapy", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "May interact with certain chemotherapeutic agents via CYP3A4 modulation.", "note": None},
    ],
    "allicin": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive antiplatelet effect may potentiate bleeding risk.", "note": None},
    ],
    "garlic": [
        {"drug_name": "Warfarin", "severity": SafetyRiskLevel.MODERATE,
         "mechanism": "Additive antiplatelet effect may potentiate bleeding risk.", "note": None},
    ],
}

# contraindication_key -> list of intervention names (lowercase) excluded outright
_CONTRAINDICATIONS: dict[str, list[str]] = {
    "pregnancy": ["berberine", "ashwagandha", "curcumin", "boswellia serrata"],
    "severe_ckd": ["magnesium", "potassium", "vitamin d"],
    "autoimmune_on_immunosuppressants": ["ashwagandha", "echinacea"],
}

# intervention name (lowercase) -> regulation note
_REGULATED_INTERVENTIONS: dict[str, str] = {
    "bpc-157": "BPC-157 is an investigational peptide with no FDA-approved indication. "
    "Surfaced for evidence context only; not a recommendation to self-administer.",
    "tb-500": "TB-500 is an investigational peptide with no FDA-approved indication. "
    "Surfaced for evidence context only; not a recommendation to self-administer.",
    "semaglutide": "Semaglutide is a prescription-only GLP-1 receptor agonist. "
    "Surfaced for evidence context only; requires a physician's prescription.",
    "tirzepatide": "Tirzepatide is a prescription-only GIP/GLP-1 receptor agonist. "
    "Surfaced for evidence context only; requires a physician's prescription.",
}

_PREGNANCY_CONDITION_RE = re.compile(r"\bpregnan", re.IGNORECASE)
_CKD_CONDITION_RE = re.compile(r"\b(severe\s+)?(chronic\s+kidney\s+disease|ckd|renal\s+failure)\b", re.IGNORECASE)
_AUTOIMMUNE_CONDITION_RE = re.compile(
    r"\b(lupus|rheumatoid\s+arthritis|multiple\s+sclerosis|autoimmune|crohn|hashimoto)", re.IGNORECASE
)
_IMMUNOSUPPRESSANT_RE = re.compile(
    r"\b(immunosuppressant|cyclosporine|tacrolimus|azathioprine|methotrexate|biologic)", re.IGNORECASE
)


def _active_contraindication_keys(health_profile: dict) -> set[str]:
    conditions = " ".join(health_profile.get("known_conditions", []) or [])
    medications = " ".join(health_profile.get("current_medications", []) or [])

    active: set[str] = set()
    if _PREGNANCY_CONDITION_RE.search(conditions):
        active.add("pregnancy")
    if _CKD_CONDITION_RE.search(conditions):
        active.add("severe_ckd")
    if _AUTOIMMUNE_CONDITION_RE.search(conditions) and _IMMUNOSUPPRESSANT_RE.search(medications):
        active.add("autoimmune_on_immunosuppressants")
    return active


def _matched_drug_interactions(intervention_name: str, medications: list[str]) -> list[dict]:
    entries = _DRUG_HERB_INTERACTIONS.get(intervention_name.lower(), [])
    if not entries or not medications:
        return []
    medications_lower = [m.lower() for m in medications]
    matched = []
    for entry in entries:
        drug_key = entry["drug_name"].lower()
        drug_tokens = re.split(r"[/,]|\s+or\s+", drug_key)
        if any(any(token.strip() in med for token in drug_tokens if token.strip()) for med in medications_lower):
            matched.append(entry)
    return matched


_SEVERITY_ORDER = [
    SafetyRiskLevel.LOW,
    SafetyRiskLevel.MODERATE,
    SafetyRiskLevel.HIGH,
    SafetyRiskLevel.CONTRAINDICATED,
]


def check_safety(recommendations: list[LLMRecommendation], health_profile: dict) -> SafetyReport:
    """Stage 6 entry point: score each recommendation's safety risk and exclude contraindications."""
    medications = health_profile.get("current_medications", []) or []
    contraindication_keys = _active_contraindication_keys(health_profile)
    contraindicated_names = {
        name for key in contraindication_keys for name in _CONTRAINDICATIONS.get(key, [])
    }

    approved: list[ScoredRecommendation] = []
    excluded: list[ScoredRecommendation] = []
    high_risk_names: list[str] = []

    for rec in recommendations:
        name_lower = rec.intervention_name.lower()
        is_regulated = name_lower in _REGULATED_INTERVENTIONS
        regulation_note = _REGULATED_INTERVENTIONS.get(name_lower)

        if name_lower in contraindicated_names:
            excluded.append(
                ScoredRecommendation(
                    **rec.model_dump(),
                    safety_risk=SafetyRiskLevel.CONTRAINDICATED,
                    safety_notes=["Excluded: contraindicated given patient's health profile."],
                    interactions=[],
                    is_regulated=is_regulated,
                )
            )
            continue

        interactions = _matched_drug_interactions(rec.intervention_name, medications)
        if interactions:
            worst = max(interactions, key=lambda i: _SEVERITY_ORDER.index(i["severity"]))
            safety_risk = worst["severity"]
        else:
            safety_risk = SafetyRiskLevel.LOW

        safety_notes = []
        if regulation_note:
            safety_notes.append(regulation_note)
        interaction_labels = [
            f"{i['drug_name']}: {i['mechanism']}" + (f" ({i['note']})" if i.get("note") else "")
            for i in interactions
        ]

        if safety_risk in (SafetyRiskLevel.MODERATE, SafetyRiskLevel.HIGH):
            high_risk_names.append(rec.intervention_name)

        approved.append(
            ScoredRecommendation(
                **rec.model_dump(),
                safety_risk=safety_risk,
                safety_notes=safety_notes,
                interactions=interaction_labels,
                is_regulated=is_regulated,
            )
        )

    requires_review = bool(excluded) or bool(high_risk_names)
    overall_note = (
        "No major drug-herb interactions detected."
        if not high_risk_names and not excluded
        else "One or more recommendations require clinician review before starting."
    )

    return SafetyReport(
        approved_recommendations=approved,
        excluded_recommendations=excluded,
        requires_clinician_review=requires_review,
        overall_note=overall_note,
    )
