"""Report-level clinician-trust insights — evidence maturity, missing data, honest confidence."""

from __future__ import annotations

from app.models.enums import EVIDENCE_CONFIDENCE_LABELS, EVIDENCE_TIER_LABELS, EvidenceConfidenceLevel, EvidenceTier
from app.schemas.explainability import RecommendationExplainability

# Biomarkers that would strengthen interpretation when absent from the panel.
SYSTEM_EXPECTED_BIOMARKERS: dict[str, list[str]] = {
    "inflammation": ["hs-CRP", "CRP", "ESR", "Ferritin"],
    "metabolic_health": ["Glucose", "HbA1c", "Insulin", "Triglycerides"],
    "cardiovascular_risk": ["LDL Cholesterol", "HDL Cholesterol", "Triglycerides", "ApoB", "hs-CRP"],
    "liver_detox_stress": ["ALT", "AST", "GGT", "Bilirubin, Total"],
    "nutrient_status": ["Ferritin", "Vitamin D, 25-OH", "Vitamin B12", "Folate"],
    "thyroid_endocrine": ["TSH", "Free T4", "Free T3", "Cortisol"],
    "oxidative_stress_mitochondrial": ["GGT", "Uric Acid", "Vitamin D, 25-OH"],
}

_REPORT_WIDE_SUGGESTIONS = [
    "Ferritin",
    "Vitamin D, 25-OH",
    "Vitamin B12",
    "Folate",
    "hs-CRP",
    "CRP",
    "HbA1c",
    "ApoB",
]

_BIOMARKER_BASE_PRIORITY: dict[str, int] = {
    "Ferritin": 50,
    "hs-CRP": 48,
    "CRP": 47,
    "ApoB": 45,
    "Insulin": 44,
    "Fasting Insulin": 44,
    "HbA1c": 42,
    "Glucose": 40,
    "Transferrin Saturation": 38,
    "TIBC": 36,
    "Vitamin D, 25-OH": 34,
    "Vitamin B12": 32,
    "Folate": 30,
    "ESR": 28,
    "Free T4": 26,
    "Free T3": 24,
    "Reticulocyte Count": 22,
}

_IRON_PANEL_MARKERS = frozenset({"Iron", "Ferritin", "TIBC", "Transferrin Saturation", "Reticulocyte Count"})

_BIOMARKER_DIFFERENTIALS: dict[str, dict] = {
    "Iron": {
        "statuses": ("critical_low", "low"),
        "primary": {
            "explanation": "Iron deficiency",
            "support": "high",
            "supported_by": "Low iron with iron/hepcidin pathway signal",
        },
        "alternatives": [
            {
                "explanation": "Anemia of chronic disease",
                "support": "low",
                "reason": "Ferritin and inflammatory markers unavailable — cannot rule out inflammation-driven iron sequestration",
                "missing_markers": ["Ferritin", "CRP", "hs-CRP"],
            },
            {
                "explanation": "Thalassemia trait / hemoglobinopathy",
                "support": "low",
                "reason": "Red-cell indices and hemoglobin pattern not available in this panel",
                "missing_markers": ["MCV", "MCH", "Hemoglobin"],
            },
        ],
    },
    "Ferritin": {
        "statuses": ("critical_low", "low"),
        "primary": {
            "explanation": "Iron store depletion",
            "support": "high",
            "supported_by": "Low ferritin consistent with depleted iron stores",
        },
        "alternatives": [
            {
                "explanation": "Inflammation-driven ferritin elevation masked by concurrent deficiency",
                "support": "low",
                "reason": "CRP/ESR unavailable — cannot assess inflammatory contribution",
                "missing_markers": ["CRP", "hs-CRP", "ESR"],
            },
        ],
    },
    "TSH": {
        "statuses": ("critical_high", "high"),
        "primary": {
            "explanation": "Hypothyroid pattern",
            "support": "high",
            "supported_by": "Elevated TSH with thyroid/endocrine pathway signal",
        },
        "alternatives": [
            {
                "explanation": "Subclinical hypothyroidism vs non-thyroidal illness",
                "support": "low",
                "reason": "Free T4 and Free T3 unavailable — cannot confirm peripheral hormone status",
                "missing_markers": ["Free T4", "Free T3"],
            },
        ],
    },
    "Glucose": {
        "statuses": ("critical_high", "high"),
        "primary": {
            "explanation": "Glycemic dysregulation",
            "support": "high",
            "supported_by": "Elevated glucose with metabolic pathway signal",
        },
        "alternatives": [
            {
                "explanation": "Stress / acute illness hyperglycemia",
                "support": "low",
                "reason": "HbA1c unavailable — cannot distinguish acute vs sustained dysglycemia",
                "missing_markers": ["HbA1c"],
            },
        ],
    },
    "CRP": {
        "statuses": ("critical_high", "high"),
        "primary": {
            "explanation": "Systemic inflammation",
            "support": "high",
            "supported_by": "Elevated CRP with inflammatory pathway signal",
        },
        "alternatives": [
            {
                "explanation": "Localized infection vs chronic inflammatory condition",
                "support": "low",
                "reason": "Additional inflammatory and iron markers would clarify chronicity",
                "missing_markers": ["ESR", "Ferritin"],
            },
        ],
    },
    "hs-CRP": {
        "statuses": ("critical_high", "high"),
        "primary": {
            "explanation": "Systemic inflammation",
            "support": "high",
            "supported_by": "Elevated hs-CRP with inflammatory pathway signal",
        },
        "alternatives": [
            {
                "explanation": "Localized infection vs chronic inflammatory condition",
                "support": "low",
                "reason": "Additional inflammatory and iron markers would clarify chronicity",
                "missing_markers": ["ESR", "Ferritin"],
            },
        ],
    },
}

_STRENGTHENING_BY_CONTEXT: dict[str, list[str]] = {
    "iron_panel": ["Ferritin", "Transferrin Saturation", "Reticulocyte Count", "TIBC"],
    "inflammation": ["hs-CRP", "CRP", "ESR", "Ferritin"],
    "metabolic": ["HbA1c", "Fasting Insulin", "Glucose", "Triglycerides"],
    "thyroid": ["Free T4", "Free T3", "TSH"],
    "cardiovascular": ["ApoB", "LDL Cholesterol", "Triglycerides", "hs-CRP"],
}


def _measured_names(biomarker_summary: dict) -> set[str]:
    return {m["biomarker_name"] for m in biomarker_summary.get("measured_biomarkers", [])}


def _abnormal_biomarkers(biomarker_summary: dict) -> list[dict]:
    abnormal_statuses = {"critical_low", "low", "high", "critical_high"}
    return [
        m
        for m in biomarker_summary.get("measured_biomarkers", [])
        if m.get("status") in abnormal_statuses
    ]


def _priority_stars(score: int) -> int:
    if score >= 55:
        return 5
    if score >= 45:
        return 4
    if score >= 35:
        return 3
    if score >= 25:
        return 2
    return 1


def _rank_missing_biomarkers(
    suggestions: list[str],
    biomarker_summary: dict,
    biological_systems: list[dict],
) -> list[dict]:
    measured = _measured_names(biomarker_summary)
    abnormal_names = {m["biomarker_name"] for m in _abnormal_biomarkers(biomarker_summary)}
    active_system_codes = {
        s.get("system_code")
        for s in biological_systems
        if (s.get("signal_level") or 0) > 0
    }

    ranked: list[dict] = []
    for biomarker in suggestions:
        score = _BIOMARKER_BASE_PRIORITY.get(biomarker, 20)
        if "Iron" in abnormal_names and biomarker in {"Ferritin", "Transferrin Saturation", "TIBC", "Reticulocyte Count"}:
            score += 25
        if biomarker in {"CRP", "hs-CRP", "ESR", "Ferritin"} and "inflammation" in active_system_codes:
            score += 15
        if biomarker in {"HbA1c", "Fasting Insulin", "Glucose"} and "metabolic_health" in active_system_codes:
            score += 15
        if biomarker in {"Free T4", "Free T3"} and "thyroid_endocrine" in active_system_codes:
            score += 15
        if biomarker in {"ApoB", "LDL Cholesterol"} and "cardiovascular_risk" in active_system_codes:
            score += 12
        for system in biological_systems:
            if biomarker in (system.get("missing_biomarkers") or []):
                score += 8
        stars = _priority_stars(score)
        ranked.append(
            {
                "biomarker_name": biomarker,
                "priority_score": score,
                "stars": stars,
                "star_label": "★" * stars + "☆" * (5 - stars),
                "measured": biomarker in measured,
            }
        )

    ranked.sort(key=lambda row: (-row["priority_score"], row["biomarker_name"]))
    return ranked


def enrich_biological_systems(systems: list[dict], measured: set[str]) -> list[dict]:
    """Label systems as Not Assessable vs No Abnormal Signal — never imply measurement without data."""
    enriched = []
    for system in systems:
        row = dict(system)
        if (row.get("signal_level") or 0) == 0:
            expected = SYSTEM_EXPECTED_BIOMARKERS.get(row.get("system_code", ""), [])
            missing = [b for b in expected if b not in measured]
            row["missing_biomarkers"] = missing
            if missing:
                row["signal_label"] = "Not Assessable"
                row["assessment_status"] = "not_assessable"
                row["no_signal_reason"] = "Key markers unavailable for this system."
                row["unavailable_markers"] = [f"{marker} unavailable" for marker in missing]
            elif row.get("drivers"):
                row["signal_label"] = "No Abnormal Signal"
                row["assessment_status"] = "measured_normal"
                row["no_signal_reason"] = "Relevant markers measured and within reference range."
            else:
                row["signal_label"] = "Not Assessable"
                row["assessment_status"] = "not_assessable"
                row["no_signal_reason"] = "No contributing biomarkers mapped to this system."
        else:
            row["missing_biomarkers"] = []
            row["no_signal_reason"] = None
            row["assessment_status"] = "signal_detected"
        enriched.append(row)
    return enriched


def build_evidence_summary(recommendations: list[dict]) -> dict:
    """Report-level evidence maturity — % Established / Emerging / Preclinical."""
    if not recommendations:
        return {
            "established_percent": 0.0,
            "emerging_percent": 0.0,
            "preclinical_percent": 0.0,
            "total_recommendations": 0,
            "breakdown": {},
        }

    buckets = {"established": 0, "emerging": 0, "preclinical": 0}
    for rec in recommendations:
        tier = rec.get("evidence_tier", EvidenceTier.RESEARCH_HYPOTHESIS.value)
        if isinstance(tier, EvidenceTier):
            tier = tier.value
        if tier == EvidenceTier.ESTABLISHED.value:
            buckets["established"] += 1
        elif tier == EvidenceTier.EMERGING.value:
            buckets["emerging"] += 1
        else:
            buckets["preclinical"] += 1

    total = len(recommendations)
    return {
        "established_percent": round(buckets["established"] / total * 100, 1),
        "emerging_percent": round(buckets["emerging"] / total * 100, 1),
        "preclinical_percent": round(buckets["preclinical"] / total * 100, 1),
        "total_recommendations": total,
        "breakdown": {
            EVIDENCE_TIER_LABELS[EvidenceTier.ESTABLISHED]: buckets["established"],
            EVIDENCE_TIER_LABELS[EvidenceTier.EMERGING]: buckets["emerging"],
            "Preclinical / Hypothesis": buckets["preclinical"],
        },
    }


def build_missing_information(
    biomarker_summary: dict,
    biological_systems: list[dict],
    explainability_items: list[RecommendationExplainability] | None = None,
) -> dict:
    """Biomarkers that would improve pathway interpretation and confidence."""
    measured = _measured_names(biomarker_summary)
    suggestions: list[str] = []

    for system in biological_systems:
        for biomarker in system.get("missing_biomarkers") or []:
            if biomarker not in measured and biomarker not in suggestions:
                suggestions.append(biomarker)

    for candidate in _REPORT_WIDE_SUGGESTIONS:
        if candidate not in measured and candidate not in suggestions:
            suggestions.append(candidate)

    if explainability_items:
        for item in explainability_items:
            for gap in item.research_gaps:
                if gap.gap.startswith("Missing ") and "measurement" in gap.gap:
                    name = gap.gap.replace("Missing ", "").split(" measurement")[0]
                    if name not in suggestions and name not in measured:
                        suggestions.append(name)

    ranked = _rank_missing_biomarkers(suggestions[:12], biomarker_summary, biological_systems)
    return {
        "summary": (
            "Confidence and pathway interpretation could improve by adding labs not present in this panel."
            if ranked
            else "No high-priority missing biomarkers identified for this panel."
        ),
        "suggested_biomarkers": [row["biomarker_name"] for row in ranked[:10]],
        "ranked_biomarkers": ranked[:10],
        "section_heading": "Highest Value Additional Tests",
    }


def build_overall_confidence_assessment(
    biomarker_summary: dict,
    recommendations: list[dict],
    biological_systems: list[dict] | None = None,
    missing_information: dict | None = None,
    explainability_items: list[RecommendationExplainability] | None = None,
) -> dict:
    """Hero-level report trust assessment — can I trust this report?"""
    total = biomarker_summary.get("total_biomarkers", 0)
    abnormal = biomarker_summary.get("abnormal_count", 0)
    rec_count = len(recommendations)
    systems = biological_systems or []
    missing = missing_information or {}

    if explainability_items:
        numerics = [e.evidence_confidence_numeric for e in explainability_items]
        mean_numeric = sum(numerics) / len(numerics)
        levels = [e.evidence_confidence_level for e in explainability_items]
        if levels.count(EvidenceConfidenceLevel.LOW) > len(levels) / 2:
            level = EvidenceConfidenceLevel.LOW
        elif levels.count(EvidenceConfidenceLevel.HIGH) > len(levels) / 2:
            level = EvidenceConfidenceLevel.HIGH
        else:
            level = EvidenceConfidenceLevel.MODERATE
    elif rec_count:
        mean_numeric = sum(r.get("confidence_score", 0) for r in recommendations) / rec_count
        level = (
            EvidenceConfidenceLevel.HIGH
            if mean_numeric >= 0.7
            else EvidenceConfidenceLevel.MODERATE
            if mean_numeric >= 0.45
            else EvidenceConfidenceLevel.LOW
        )
    elif total > 0 and abnormal == 0:
        mean_numeric = 0.55
        level = EvidenceConfidenceLevel.MODERATE
    else:
        mean_numeric = 0.0
        level = EvidenceConfidenceLevel.LOW

    systems_evaluated = len(systems) or 7
    systems_with_signal = sum(1 for s in systems if (s.get("signal_level") or 0) > 0)
    missing_count = len(missing.get("suggested_biomarkers") or [])

    reason_checks: list[str] = []
    if total:
        reason_checks.append(f"{total} biomarker{'s' if total != 1 else ''} analyzed")
    if systems_evaluated:
        reason_checks.append(f"{systems_evaluated} biological systems evaluated")
    if rec_count and explainability_items:
        high_evidence = sum(
            1 for e in explainability_items
            if e.evidence_confidence_level == EvidenceConfidenceLevel.HIGH
        )
        if high_evidence:
            reason_checks.append("Strong evidence available for surfaced considerations")
        else:
            reason_checks.append("Moderate evidence available for surfaced considerations")
    elif rec_count:
        reason_checks.append("Evidence-graded considerations surfaced")
    if missing_count <= 2:
        reason_checks.append("No major missing biomarkers for this panel")
    elif missing_count <= 5:
        reason_checks.append("Some biomarkers would strengthen interpretation")
    else:
        reason_checks.append("Additional biomarkers would substantially improve interpretation")

    confidence_drivers: list[str] = []
    if explainability_items and any(
        e.evidence_quality_grade.value in ("very_high", "high") for e in explainability_items
    ):
        confidence_drivers.append("High-quality evidence")
    elif rec_count:
        confidence_drivers.append("Available published evidence")
    if total >= 8:
        confidence_drivers.append("Good biomarker coverage")
    elif total >= 4:
        confidence_drivers.append("Moderate biomarker coverage")
    else:
        confidence_drivers.append("Limited biomarker coverage")
    if missing_count <= 2:
        confidence_drivers.append("Low data-gap uncertainty")
    else:
        confidence_drivers.append("Moderate data-gap uncertainty")
    if systems_with_signal >= 2:
        confidence_drivers.append("Multiple pathway signals corroborated")
    elif systems_with_signal == 1:
        confidence_drivers.append("Single dominant pathway signal")

    reasons: list[str] = []
    if total <= 3:
        reasons.append(f"Only {total} clinically relevant biomarker(s) available in this panel.")
    if abnormal == 1:
        reasons.append("Only one biomarker outside reference range — limited pathway cross-validation.")
    if abnormal > 0 and rec_count == 0:
        reasons.append("Abnormal values present but no evidence-backed considerations could be routed.")
    if total > 0 and abnormal == 0:
        reasons.append("All tracked biomarkers are within reference range.")
    if not reasons:
        reasons.append(f"{rec_count} evidence-graded consideration(s) from {abnormal} abnormal biomarker(s).")

    label = EVIDENCE_CONFIDENCE_LABELS[level]
    return {
        "confidence_level": level.value,
        "confidence_heading": "Report Confidence",
        "confidence_label": label,
        "confidence_label_upper": label.upper(),
        "confidence_numeric": round(mean_numeric, 4),
        "reasons": reasons,
        "reason_checks": reason_checks,
        "confidence_drivers": confidence_drivers,
    }


def _human_evidence_label(evidence_summary: dict, recommendations: list[dict]) -> str:
    established = evidence_summary.get("established_percent", 0)
    if established >= 50:
        return "High Human Evidence"
    if established >= 25 or recommendations:
        return "Moderate Human Evidence"
    return "Limited Human Evidence"


def build_differential_explanations(
    biomarker_summary: dict,
    pathway_activations: list[dict],
    biological_systems: list[dict],
) -> dict:
    """Possible biological explanations — not diagnoses, framed for researchers."""
    measured = _measured_names(biomarker_summary)
    abnormal = _abnormal_biomarkers(biomarker_summary)
    active_pathways = {
        p.get("pathway_code")
        for p in pathway_activations
        if (p.get("activation_score") or 0) > 0
    }
    explanations: list[dict] = []

    for marker in abnormal:
        name = marker["biomarker_name"]
        spec = _BIOMARKER_DIFFERENTIALS.get(name)
        if not spec or marker.get("status") not in spec["statuses"]:
            continue

        primary = dict(spec["primary"])
        alternatives: list[dict] = []
        for alt in spec.get("alternatives", []):
            missing = [m for m in alt.get("missing_markers", []) if m not in measured]
            alt_row = {
                "explanation": alt["explanation"],
                "support": alt["support"],
                "reason": alt["reason"],
                "missing_markers": missing,
            }
            if missing:
                alt_row["reason"] = (
                    f"{', '.join(missing)} unavailable — {alt['reason'].split('—', 1)[-1].strip()}"
                    if "—" in alt["reason"]
                    else f"{', '.join(missing)} unavailable — {alt['reason']}"
                )
            alternatives.append(alt_row)

        explanations.append(
            {
                "biomarker_name": name,
                "status": marker.get("status"),
                "most_likely": primary,
                "alternatives": alternatives,
                "pathway_codes": sorted(active_pathways)[:4],
            }
        )

    if not explanations and abnormal:
        top = abnormal[0]
        explanations.append(
            {
                "biomarker_name": top["biomarker_name"],
                "status": top.get("status"),
                "most_likely": {
                    "explanation": f"Biological signal from abnormal {top['biomarker_name']}",
                    "support": "moderate",
                    "supported_by": "Abnormal biomarker with pathway-linked evidence synthesis",
                },
                "alternatives": [
                    {
                        "explanation": "Alternative mechanisms require additional markers",
                        "support": "low",
                        "reason": "Insufficient biomarker coverage to rank competing explanations",
                        "missing_markers": [],
                    }
                ],
                "pathway_codes": sorted(active_pathways)[:4],
            }
        )

    active_systems = [s["system_name"] for s in biological_systems if (s.get("signal_level") or 0) > 0]
    return {
        "heading": "Possible Biological Explanations",
        "disclaimer": "Not a diagnosis — competing biological explanations given available data.",
        "explanations": explanations,
        "active_systems": active_systems,
    }


def build_patient_evidence_gaps(
    biomarker_summary: dict,
    missing_information: dict,
    overall_confidence: dict,
    pathway_activations: list[dict],
) -> dict:
    """Patient-specific evidence gaps — what would strengthen interpretation for this panel."""
    measured = _measured_names(biomarker_summary)
    abnormal_names = {m["biomarker_name"] for m in _abnormal_biomarkers(biomarker_summary)}
    reasons: list[str] = []
    strengthening: list[str] = []

    iron_measured = _IRON_PANEL_MARKERS & measured
    if iron_measured and "Iron" in abnormal_names and len(iron_measured) <= 2:
        reasons.append("Only limited iron-related markers available in this panel.")
        strengthening.extend(_STRENGTHENING_BY_CONTEXT["iron_panel"])

    if "inflammation" in {
        p.get("pathway_code") for p in pathway_activations if (p.get("activation_score") or 0) > 0
    } or {"CRP", "hs-CRP"} & abnormal_names:
        if not ({"CRP", "hs-CRP", "ESR"} & measured):
            reasons.append("Inflammatory markers are incomplete for this panel.")
            strengthening.extend(_STRENGTHENING_BY_CONTEXT["inflammation"])

    if {"Glucose", "HbA1c"} & abnormal_names and "HbA1c" not in measured:
        reasons.append("Glycemic markers are incomplete — acute vs sustained dysglycemia cannot be distinguished.")
        strengthening.extend(_STRENGTHENING_BY_CONTEXT["metabolic"])

    if "TSH" in abnormal_names and not ({"Free T4", "Free T3"} & measured):
        reasons.append("Thyroid panel is incomplete — peripheral hormone status not confirmed.")
        strengthening.extend(_STRENGTHENING_BY_CONTEXT["thyroid"])

    for row in missing_information.get("ranked_biomarkers") or []:
        if row["biomarker_name"] not in strengthening and row.get("stars", 0) >= 4:
            strengthening.append(row["biomarker_name"])

    if biomarker_summary.get("total_biomarkers", 0) <= 3:
        reasons.append(
            f"Only {biomarker_summary.get('total_biomarkers', 0)} clinically relevant biomarker(s) available in this panel."
        )

    if not reasons and overall_confidence.get("reasons"):
        reasons.append(overall_confidence["reasons"][0])

    deduped_strengthening: list[str] = []
    for marker in strengthening:
        if marker not in measured and marker not in deduped_strengthening:
            deduped_strengthening.append(marker)

    certainty = overall_confidence.get("confidence_label", "Moderate")
    return {
        "heading": "Evidence Gaps",
        "subheading": "For this patient panel",
        "certainty_label": certainty,
        "certainty_heading": "Current certainty",
        "reasons": reasons[:4],
        "strengthening_tests": deduped_strengthening[:8],
        "summary": (
            f"{certainty} biological interpretation confidence — additional markers would strengthen pathway cross-validation."
            if deduped_strengthening
            else f"{certainty} biological interpretation confidence for the available panel."
        ),
    }


def build_biological_reasoning_summary(
    biomarker_summary: dict,
    biological_systems: list[dict],
    pathway_activations: list[dict],
    recommendations: list[dict],
    evidence_summary: dict,
    missing_information: dict,
) -> dict:
    """Signature visual cascade — one graphic explains the report."""
    measured = biomarker_summary.get("measured_biomarkers", [])
    abnormal = [m["biomarker_name"] for m in measured if m.get("status") not in ("normal", "optimal")]
    active_systems = [s["system_name"] for s in biological_systems if (s.get("signal_level") or 0) > 0]
    pathways = sorted({p.get("pathway_name") for p in pathway_activations if p.get("pathway_name")})
    interventions = [r.get("intervention_name") for r in recommendations[:8]]

    primary_finding = abnormal[0] if abnormal else (measured[0]["biomarker_name"] if measured else "No biomarkers parsed")
    primary_system = active_systems[0] if active_systems else (
        biological_systems[0]["system_name"] if biological_systems else "Biological systems screened"
    )
    primary_pathway = pathways[0] if pathways else "No pathway activated"
    evidence_label = _human_evidence_label(evidence_summary, recommendations)
    intervention_label = ", ".join(interventions[:3]) if interventions else "No considerations surfaced"

    visual_chain = [
        {"kind": "finding", "label": primary_finding},
        {"kind": "system", "label": primary_system},
        {"kind": "pathway", "label": primary_pathway},
        {"kind": "evidence", "label": evidence_label},
        {"kind": "interventions", "label": intervention_label},
    ]

    return {
        "visual_chain": visual_chain,
        "cascade": [
            {"step": "measured_biomarkers", "label": "Measured Biomarkers", "items": [m["biomarker_name"] for m in measured[:12]]},
            {"step": "abnormal_findings", "label": "Abnormal Findings", "items": abnormal},
            {"step": "biological_systems", "label": "Biological Systems", "items": active_systems or ["Not assessable from current panel"]},
            {"step": "pathways", "label": "Pathways", "items": pathways[:8] or ["No pathways activated"]},
            {"step": "evidence_maturity", "label": "Evidence Maturity", "items": [
                f"Established {evidence_summary.get('established_percent', 0)}%",
                f"Emerging {evidence_summary.get('emerging_percent', 0)}%",
                f"Preclinical {evidence_summary.get('preclinical_percent', 0)}%",
            ]},
            {"step": "interventions", "label": "Evidence-Based Considerations", "items": interventions or ["None surfaced"]},
            {"step": "research_gaps", "label": "Research Gaps / Missing Data", "items": missing_information.get("suggested_biomarkers", [])[:6]},
        ],
    }


def build_report_insights(
    biomarker_summary: dict,
    biological_systems: list[dict],
    pathway_activations: list[dict],
    recommendations: list[dict],
    explainability_items: list[RecommendationExplainability] | None = None,
    *,
    citations: list[dict] | None = None,
) -> dict:
    measured = _measured_names(biomarker_summary)
    systems = enrich_biological_systems(biological_systems, measured)
    evidence_summary = build_evidence_summary(recommendations)
    missing_information = build_missing_information(biomarker_summary, systems, explainability_items)
    overall_confidence = build_overall_confidence_assessment(
        biomarker_summary,
        recommendations,
        biological_systems=systems,
        missing_information=missing_information,
        explainability_items=explainability_items,
    )
    biological_reasoning_summary = build_biological_reasoning_summary(
        biomarker_summary,
        systems,
        pathway_activations,
        recommendations,
        evidence_summary,
        missing_information,
    )
    differential_explanations = build_differential_explanations(
        biomarker_summary,
        pathway_activations,
        systems,
    )
    patient_evidence_gaps = build_patient_evidence_gaps(
        biomarker_summary,
        missing_information,
        overall_confidence,
        pathway_activations,
    )
    from app.pipeline.report_methodology import build_report_methodology

    report_methodology = build_report_methodology(
        biomarker_summary,
        systems,
        pathway_activations,
        recommendations,
        citations=citations,
    )
    return {
        "evidence_summary": evidence_summary,
        "missing_information": missing_information,
        "overall_confidence_assessment": overall_confidence,
        "biological_reasoning_summary": biological_reasoning_summary,
        "biological_systems": systems,
        "differential_explanations": differential_explanations,
        "patient_evidence_gaps": patient_evidence_gaps,
        "report_methodology": report_methodology,
    }


def insights_from_stored_report(
    biomarker_summary: dict,
    biological_systems: list[dict],
    pathway_activations: list[dict],
    recommendations: list[dict],
    explainability_items: list[RecommendationExplainability] | None = None,
    *,
    citations: list[dict] | None = None,
) -> dict:
    """Recompute clinician-trust insights for persisted reports (e.g. pre-migration payloads)."""
    base_systems = [
        {k: v for k, v in s.items() if k not in ("missing_biomarkers", "no_signal_reason", "assessment_status")}
        for s in (biological_systems or [])
    ]
    if not base_systems:
        from app.pipeline.biological_systems import compute_biological_systems
        from app.schemas.pipeline import PathwayActivation

        activations = [PathwayActivation(**p) for p in pathway_activations]
        base_systems = compute_biological_systems(activations)
    return build_report_insights(
        biomarker_summary,
        base_systems,
        pathway_activations,
        recommendations,
        explainability_items=explainability_items,
        citations=citations,
    )