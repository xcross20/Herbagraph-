"""Dual rankings: root clinical priorities vs highest network leverage."""

from __future__ import annotations

from app.knowledge_graph.lifestyle_evidence import LIFESTYLE_EVIDENCE_CLAIMS
from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
from app.models.enums import DisplayIntent, EvidenceLevel, EvidenceTier
from app.pipeline.biological_systems import SYSTEM_PATHWAYS
from app.pipeline.report_biological_hierarchy import (
    _enrich_intervention_row,
    _pathway_activation_index,
    evidence_grade_for,
)
from app.pipeline.report_intent import REGULATED_CATEGORIES, classify_display_intent

_ALL_CLAIMS = [*EVIDENCE_CLAIMS, *TIER_A_EVIDENCE_CLAIMS, *LIFESTYLE_EVIDENCE_CLAIMS]

_STATUS_SEVERITY = {
    "critical_low": 1.0,
    "critical_high": 1.0,
    "low": 0.72,
    "high": 0.55,
}

_CLINICAL_IMPORTANCE = {
    "Iron": 0.95,
    "Ferritin": 0.92,
    "HbA1c": 0.88,
    "Glucose": 0.82,
    "LDL Cholesterol": 0.78,
    "LDL": 0.78,
    "CRP": 0.8,
    "hs-CRP": 0.8,
    "TSH": 0.85,
}

_TREATABILITY = {
    "Iron": 0.92,
    "Ferritin": 0.9,
    "HbA1c": 0.88,
    "Glucose": 0.85,
    "LDL Cholesterol": 0.86,
    "LDL": 0.86,
}

_PROBLEM_LABELS: dict[str, dict] = {
    "Iron": {
        "problem_label": "Iron deficiency biology",
        "severity_label_default": "High",
        "diagnostic_note": (
            "Low iron is often a clue, not the endpoint. Before emphasizing repletion, "
            "strengthen confidence with ferritin, transferrin saturation, and CRP to distinguish "
            "true iron deficiency from inflammation-related iron sequestration or alternate anemia patterns."
        ),
        "strengthening_tests": ["Ferritin", "Transferrin Saturation", "TIBC", "CRP", "hs-CRP"],
        "differential_alternatives": ["Anemia of chronic disease", "Thalassemia trait / hemoglobinopathy"],
    },
    "Ferritin": {
        "problem_label": "Iron store depletion",
        "severity_label_default": "High",
        "diagnostic_note": (
            "Low ferritin suggests depleted iron stores, but CRP/ESR help rule out inflammatory contribution "
            "before treating as straightforward deficiency."
        ),
        "strengthening_tests": ["Transferrin Saturation", "TIBC", "CRP", "hs-CRP", "Iron"],
        "differential_alternatives": ["Inflammation-driven iron sequestration"],
    },
    "HbA1c": {
        "problem_label": "Prediabetes / insulin resistance",
        "severity_label_default": "Moderate",
        "diagnostic_note": (
            "Mildly elevated HbA1c suggests sustained glycemic stress. Fasting insulin and repeat glucose "
            "help clarify insulin resistance severity and acute vs chronic dysglycemia."
        ),
        "strengthening_tests": ["Fasting Insulin", "Glucose", "Triglycerides", "ApoB"],
        "differential_alternatives": ["Stress / acute illness hyperglycemia"],
    },
    "Glucose": {
        "problem_label": "Glycemic dysregulation",
        "severity_label_default": "Moderate",
        "diagnostic_note": "HbA1c helps distinguish sustained dysglycemia from acute elevation.",
        "strengthening_tests": ["HbA1c", "Fasting Insulin", "Triglycerides"],
        "differential_alternatives": ["Stress / acute illness hyperglycemia"],
    },
    "LDL Cholesterol": {
        "problem_label": "Mild LDL elevation",
        "severity_label_default": "Mild",
        "diagnostic_note": (
            "Mild LDL elevation is common and context-dependent. ApoB and triglycerides refine "
            "cardiovascular risk framing beyond LDL alone."
        ),
        "strengthening_tests": ["ApoB", "Triglycerides", "hs-CRP"],
        "differential_alternatives": ["Familial hyperlipidemia pattern", "Secondary dyslipidemia"],
    },
    "LDL": {
        "problem_label": "Mild LDL elevation",
        "severity_label_default": "Mild",
        "diagnostic_note": (
            "Mild LDL elevation is common and context-dependent. ApoB and triglycerides refine "
            "cardiovascular risk framing beyond LDL alone."
        ),
        "strengthening_tests": ["ApoB", "Triglycerides", "hs-CRP"],
        "differential_alternatives": ["Familial hyperlipidemia pattern", "Secondary dyslipidemia"],
    },
}

_NETWORK_GROUPS: list[dict] = [
    {
        "group_code": "metabolic_network",
        "label": "Metabolic Network",
        "system_code": "metabolic_health",
        "pathway_codes": ["INSULIN_PI3K_AKT", "AMPK", "GLP1_INCRETINS"],
    },
    {
        "group_code": "lipid_network",
        "label": "Cardiovascular / Lipid Network",
        "system_code": "cardiovascular_risk",
        "pathway_codes": ["HEPATIC_LIPID", "PURINE_URIC_ACID", "RENAL_FILTRATION"],
    },
    {
        "group_code": "nutrient_network",
        "label": "Nutrient / Iron Network",
        "system_code": "nutrient_status",
        "pathway_codes": ["IRON_HEPCIDIN", "NUTRIENT_DEFICIENCY", "ONE_CARBON_METHYLATION"],
    },
    {
        "group_code": "inflammation_network",
        "label": "Inflammation Network",
        "system_code": "inflammation",
        "pathway_codes": ["NF_KB", "IL6_JAK_STAT3"],
    },
]


def _abnormal_biomarkers(biomarker_summary: dict) -> list[dict]:
    abnormal_statuses = {"critical_low", "low", "high", "critical_high"}
    return [
        m
        for m in biomarker_summary.get("measured_biomarkers", [])
        if m.get("status") in abnormal_statuses
    ]


def _measured_names(biomarker_summary: dict) -> set[str]:
    return {m["biomarker_name"] for m in biomarker_summary.get("measured_biomarkers", [])}


def _priority_stars(score: float) -> int:
    if score >= 0.82:
        return 5
    if score >= 0.68:
        return 4
    if score >= 0.52:
        return 3
    if score >= 0.38:
        return 2
    return 1


def _deviation_score(marker: dict) -> float:
    status = marker.get("status", "")
    value = marker.get("value")
    low = marker.get("reference_range_low")
    high = marker.get("reference_range_high")
    if value is None:
        return _STATUS_SEVERITY.get(status, 0.45)

    if status in ("low", "critical_low") and low is not None and low > 0:
        return min(1.0, max(0.25, (low - value) / low))
    if status in ("high", "critical_high") and high is not None and high > 0:
        return min(1.0, max(0.2, (value - high) / high))
    return _STATUS_SEVERITY.get(status, 0.45)


def _severity_label(marker: dict, spec: dict) -> str:
    score = max(_STATUS_SEVERITY.get(marker.get("status", ""), 0.45), _deviation_score(marker))
    if score >= 0.85:
        return "High"
    if score >= 0.55:
        return "Moderate"
    if score >= 0.35:
        return spec.get("severity_label_default", "Mild")
    return "Mild"


def _pathway_confidence_for_biomarker(biomarker_name: str, pathway_activations: list[dict]) -> float:
    scores = [
        float(p.get("activation_score") or 0.0)
        for p in pathway_activations
        if biomarker_name in (p.get("contributing_biomarkers") or [])
    ]
    return max(scores) if scores else 0.45


def _confidence_label(score: float) -> str:
    if score >= 0.65:
        return "High"
    if score >= 0.35:
        return "Moderate"
    return "Low"


def _treatability_label(score: float) -> str:
    if score >= 0.8:
        return "High"
    if score >= 0.55:
        return "Moderate"
    return "Low"


def _clinical_priority_score(marker: dict, pathway_activations: list[dict]) -> float:
    name = marker["biomarker_name"]
    severity = max(_STATUS_SEVERITY.get(marker.get("status", ""), 0.45), _deviation_score(marker))
    importance = _CLINICAL_IMPORTANCE.get(name, 0.6)
    confidence = _pathway_confidence_for_biomarker(name, pathway_activations)
    treatability = _TREATABILITY.get(name, 0.65)
    return round(
        severity * 0.35 + _deviation_score(marker) * 0.2 + importance * 0.2 + confidence * 0.15 + treatability * 0.1,
        4,
    )


def _interventions_for_biomarker(
    biomarker_name: str,
    recommendations: list[dict],
    abnormal_names: set[str],
    *,
    limit: int = 5,
) -> list[dict]:
    direct: list[tuple[int, float, dict]] = []
    for rec in recommendations:
        if classify_display_intent(rec, abnormal_names) == DisplayIntent.REGULATED.value:
            continue
        name = rec.get("intervention_name", "")
        claims = [
            c
            for c in _ALL_CLAIMS
            if c["intervention_name"] == name and c.get("biomarker_name") == biomarker_name
        ]
        if not claims:
            continue
        intent_rank = {"primary": 0, "nutritional_repletion": 1, "collateral": 2}.get(
            claims[0].get("recommendation_intent", "collateral"),
            3,
        )
        evidence_rank = {"high": 0, "moderate": 1, "low": 2, "preclinical": 3}.get(
            claims[0].get("evidence_level", "low"),
            3,
        )
        direct.append((intent_rank, evidence_rank, rec))

    direct.sort(key=lambda row: (row[0], row[1], -(row[2].get("network_rank_score") or row[2].get("confidence_score") or 0)))
    results: list[dict] = []
    seen: set[str] = set()
    for _, _, rec in direct:
        key = (rec.get("intervention_name") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "kind": "intervention",
                "label": rec.get("intervention_name"),
                "category": rec.get("category"),
                "evidence_grade": rec.get("evidence_grade") or evidence_grade_for(rec),
                "clinical_tags": intervention_clinical_tags(rec, biomarker_name),
            }
        )
        if len(results) >= limit:
            break
    return results


_TEST_CONFIDENCE_INCREMENTS = (5, 3, 2, 1, 1)


def intervention_clinical_tags(rec: dict, biomarker_name: str) -> list[str]:
    """Clinician-facing decision aids instead of internal pathway metrics."""
    tags: list[str] = []
    name = rec.get("intervention_name", "")
    problem = _PROBLEM_LABELS.get(biomarker_name, {}).get("problem_label", biomarker_name).lower()

    if any(
        c.get("biomarker_name") == biomarker_name
        for c in _ALL_CLAIMS
        if c.get("intervention_name") == name
    ):
        if "iron" in problem:
            tags.append("Directly targets iron metabolism")
        elif "prediabetes" in problem or "glycemic" in problem:
            tags.append("Directly targets glycemic signaling")
        elif "ldl" in problem or "lipid" in problem:
            tags.append("Directly targets lipid metabolism")
        else:
            tags.append(f"Directly relevant to {biomarker_name}")

    tier = rec.get("evidence_tier", "")
    if hasattr(tier, "value"):
        tier = tier.value
    level = rec.get("evidence_level", "")
    if hasattr(level, "value"):
        level = level.value

    if tier == EvidenceTier.ESTABLISHED.value or level == EvidenceLevel.HIGH.value:
        tags.append("Human RCT evidence")
    elif tier == EvidenceTier.EMERGING.value:
        tags.append("Emerging human evidence")
    else:
        tags.append("Limited human evidence")

    safety = str(rec.get("safety_risk", "low")).lower()
    if safety == "low":
        tags.append("Low risk")
    elif safety == "moderate":
        tags.append("Moderate risk — review advised")
    else:
        tags.append("Higher risk — clinician review")
    return tags[:4]


def diagnostic_next_steps(spec: dict, measured: set[str], *, limit: int = 5) -> list[dict]:
    steps: list[dict] = []
    for index, test in enumerate(spec.get("strengthening_tests", [])):
        if test in measured:
            continue
        stars = 5 if index < 4 else 4
        steps.append(
            {
                "kind": "test",
                "label": test,
                "biomarker": test,
                "priority_stars": stars,
                "star_label": "★" * stars + "☆" * (5 - stars),
                "clinical_tags": ["Improves diagnostic confidence"],
            }
        )
        if len(steps) >= limit:
            break
    return steps


def build_confidence_if_added_steps(
    primary_priority: dict | None,
    measured: set[str],
    *,
    base_confidence_percent: int | None = None,
) -> list[dict]:
    if not primary_priority:
        return []

    base = base_confidence_percent
    if base is None:
        conf_label = primary_priority.get("confidence", "Moderate")
        base = {"High": 92, "Moderate": 78, "Low": 58}.get(conf_label, 75)

    rows: list[dict] = [
        {
            "label": "Current confidence",
            "biomarker": None,
            "confidence_percent": base,
            "is_current": True,
        }
    ]
    cumulative = base
    increment_index = 0
    for test in primary_priority.get("strengthening_tests", []):
        if test in measured:
            continue
        increment = _TEST_CONFIDENCE_INCREMENTS[min(increment_index, len(_TEST_CONFIDENCE_INCREMENTS) - 1)]
        cumulative = min(99, cumulative + increment)
        rows.append(
            {
                "label": f"Add {test}",
                "biomarker": test,
                "confidence_percent": cumulative,
                "is_current": False,
            }
        )
        increment_index += 1
    return rows


def build_clinical_priorities(
    biomarker_summary: dict,
    pathway_activations: list[dict],
    recommendations: list[dict],
    *,
    enriched_recommendations: list[dict] | None = None,
) -> list[dict]:
    """Root clinical priorities — what abnormalities deserve attention first."""
    abnormal = _abnormal_biomarkers(biomarker_summary)
    measured = _measured_names(biomarker_summary)
    abnormal_names = {m["biomarker_name"] for m in abnormal}
    recs = enriched_recommendations or recommendations

    priorities: list[dict] = []
    for marker in abnormal:
        name = marker["biomarker_name"]
        spec = _PROBLEM_LABELS.get(name, {})
        confidence_score = _pathway_confidence_for_biomarker(name, pathway_activations)
        priority_score = _clinical_priority_score(marker, pathway_activations)
        stars = _priority_stars(priority_score)
        diagnostic_steps = diagnostic_next_steps(spec, measured, limit=5)
        potential_interventions = _interventions_for_biomarker(name, recs, abnormal_names, limit=5)

        priorities.append(
            {
                "rank": 0,
                "biomarker_name": name,
                "problem_label": spec.get("problem_label", f"Abnormal {name}"),
                "status": marker.get("status"),
                "value": marker.get("value"),
                "unit": marker.get("unit"),
                "severity": _severity_label(marker, spec),
                "confidence": _confidence_label(confidence_score),
                "treatability": _treatability_label(_TREATABILITY.get(name, 0.65)),
                "priority_score": priority_score,
                "priority_stars": stars,
                "star_label": "★" * stars + "☆" * (5 - stars),
                "diagnostic_note": spec.get(
                    "diagnostic_note",
                    f"Abnormal {name} activates pathway-linked biology; additional context labs may reduce uncertainty.",
                ),
                "strengthening_tests": [t for t in spec.get("strengthening_tests", []) if t not in measured],
                "differential_alternatives": spec.get("differential_alternatives", []),
                "likely_explanation": spec.get("problem_label", f"Abnormal {name}").replace(" biology", ""),
                "diagnostic_next_steps": diagnostic_steps,
                "potential_interventions": potential_interventions,
                "confidence_if_added": build_confidence_if_added_steps(
                    {
                        "confidence": _confidence_label(confidence_score),
                        "strengthening_tests": spec.get("strengthening_tests", []),
                    },
                    measured,
                ),
            }
        )

    priorities.sort(key=lambda p: (-p["priority_score"], p["biomarker_name"]))
    for index, row in enumerate(priorities, start=1):
        row["rank"] = index
    return priorities


def build_network_leverage_groups(
    recommendations: list[dict],
    intervention_pathways: dict[str, list[str]],
    pathway_activations: list[dict],
    *,
    enriched_recommendations: list[dict] | None = None,
    abnormal_names: set[str] | None = None,
    per_group: int = 5,
) -> list[dict]:
    """Highest network leverage — interventions that touch the most implicated biology."""
    recs = enriched_recommendations or recommendations
    abnormal_names = abnormal_names or set()
    pathway_index = {p["pathway_code"]: p for p in pathway_activations if (p.get("activation_score") or 0) > 0}

    groups: list[dict] = []
    for spec in _NETWORK_GROUPS:
        active_codes = [code for code in spec["pathway_codes"] if code in pathway_index]
        if not active_codes:
            continue

        candidates: list[dict] = []
        for rec in recs:
            if classify_display_intent(rec, abnormal_names) == DisplayIntent.REGULATED.value:
                continue
            codes = intervention_pathways.get(rec.get("intervention_name", ""), [])
            if not any(code in active_codes for code in codes):
                continue
            candidates.append(rec)

        candidates.sort(key=lambda r: (-(r.get("network_rank_score") or 0), r.get("rank", 999)))
        seen: set[str] = set()
        items: list[dict] = []
        for rec in candidates:
            key = (rec.get("intervention_name") or "").lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "intervention_name": rec.get("intervention_name"),
                    "category": rec.get("category"),
                    "evidence_grade": rec.get("evidence_grade") or evidence_grade_for(rec),
                    "network_rank": rec.get("network_rank"),
                    "clinical_tags": intervention_clinical_tags(
                        rec,
                        next(iter(abnormal_names), ""),
                    ) if abnormal_names else [],
                }
            )
            if len(items) >= per_group:
                break

        if not items:
            continue

        groups.append(
            {
                "group_code": spec["group_code"],
                "label": spec["label"],
                "system_code": spec["system_code"],
                "active_pathways": [
                    pathway_index[code].get("pathway_name", code) for code in active_codes[:4]
                ],
                "interventions": items,
            }
        )

    return groups


def _enriched_recommendations(
    recommendations: list[dict],
    intervention_pathways: dict[str, list[str]],
    pathway_activations: list[dict],
    abnormal_names: set[str],
) -> list[dict]:
    pathway_index = _pathway_activation_index(pathway_activations)
    enriched = [
        _enrich_intervention_row(rec, intervention_pathways, pathway_index, abnormal_names)
        for rec in recommendations
    ]
    enriched.sort(key=lambda r: (-r.get("network_rank_score", 0), r.get("rank", 999)))
    for index, row in enumerate(enriched, start=1):
        row["network_rank"] = index
    return enriched


def build_dual_clinical_rankings(
    biomarker_summary: dict,
    biological_systems: list[dict],
    pathway_activations: list[dict],
    recommendations: list[dict],
    intervention_pathways: dict[str, list[str]],
) -> dict:
    """Dual ranking model for report presentation."""
    abnormal_names = {m["biomarker_name"] for m in _abnormal_biomarkers(biomarker_summary)}
    recs = _enriched_recommendations(
        recommendations,
        intervention_pathways,
        pathway_activations,
        abnormal_names,
    )
    clinical_priorities = build_clinical_priorities(
        biomarker_summary,
        pathway_activations,
        recommendations,
        enriched_recommendations=recs,
    )
    network_leverage_groups = build_network_leverage_groups(
        recommendations,
        intervention_pathways,
        pathway_activations,
        enriched_recommendations=recs,
        abnormal_names=abnormal_names,
    )
    primary = clinical_priorities[0] if clinical_priorities else None
    return {
        "model": "dual_ranking_v1",
        "positioning": "AI Clinical Reasoning for Precision Nutrition",
        "clinical_priorities": clinical_priorities,
        "network_leverage_groups": network_leverage_groups,
        "confidence_if_added": (primary or {}).get("confidence_if_added", []),
        "clinical_priority_table": [
            {
                "problem": p["problem_label"],
                "severity": p["severity"],
                "confidence": p["confidence"],
                "treatability": p["treatability"],
                "priority_stars": p["priority_stars"],
                "star_label": p["star_label"],
            }
            for p in clinical_priorities
        ],
        "ranking_questions": {
            "clinical_priorities": "What abnormalities deserve attention first?",
            "network_leverage": "What interventions improve the greatest amount of biology?",
        },
    }