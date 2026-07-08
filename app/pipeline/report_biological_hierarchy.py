"""Biology-first hierarchical report model — biomarkers → systems → pathways → interventions.

Ranks by network influence on implicated biology, not raw evidence popularity alone.
"""

from __future__ import annotations

from app.models.enums import DisplayIntent, EvidenceLevel, EvidenceTier, InterventionCategory
from app.pipeline.biological_systems import SYSTEM_NAMES, SYSTEM_PATHWAYS
from app.pipeline.pathway_mapper import PATHWAY_DISPLAY_NAMES
from app.pipeline.report_intent import REGULATED_CATEGORIES, classify_display_intent

_EVIDENCE_GRADE: dict[tuple[str, str], str] = {
    (EvidenceTier.ESTABLISHED.value, EvidenceLevel.HIGH.value): "A+",
    (EvidenceTier.ESTABLISHED.value, EvidenceLevel.MODERATE.value): "A",
    (EvidenceTier.ESTABLISHED.value, EvidenceLevel.LOW.value): "A-",
    (EvidenceTier.EMERGING.value, EvidenceLevel.HIGH.value): "B+",
    (EvidenceTier.EMERGING.value, EvidenceLevel.MODERATE.value): "B",
    (EvidenceTier.EMERGING.value, EvidenceLevel.LOW.value): "B-",
    (EvidenceTier.PRECLINICAL.value, EvidenceLevel.MODERATE.value): "C+",
    (EvidenceTier.PRECLINICAL.value, EvidenceLevel.LOW.value): "C",
    (EvidenceTier.RESEARCH_HYPOTHESIS.value, EvidenceLevel.PRECLINICAL.value): "C-",
}

_SAFETY_BONUS = {"low": 1.0, "moderate": 0.6, "high": 0.2, "contraindicated": 0.0}

_INTERVENTION_CLASS_LABELS: dict[str, str] = {
    InterventionCategory.FOOD.value: "Dietary food",
    InterventionCategory.HERB.value: "Botanical",
    InterventionCategory.PHYTOCHEMICAL.value: "Dietary compound",
    InterventionCategory.SUPPLEMENT.value: "Nutraceutical",
    InterventionCategory.EXERCISE.value: "Exercise",
    InterventionCategory.SLEEP.value: "Sleep protocol",
    InterventionCategory.STRESS_REDUCTION.value: "Stress reduction",
    InterventionCategory.BEHAVIOR.value: "Lifestyle pattern",
    InterventionCategory.ENVIRONMENTAL.value: "Environmental",
}


def _abnormal_biomarkers(biomarker_summary: dict) -> list[dict]:
    abnormal_statuses = {"critical_low", "low", "high", "critical_high"}
    return [
        m
        for m in biomarker_summary.get("measured_biomarkers", [])
        if m.get("status") in abnormal_statuses
    ]


def _tier_value(tier) -> str:
    return tier.value if hasattr(tier, "value") else str(tier or EvidenceTier.RESEARCH_HYPOTHESIS.value)


def _level_value(level) -> str:
    return level.value if hasattr(level, "value") else str(level or EvidenceLevel.LOW.value)


def _category_value(category) -> str:
    return category.value if hasattr(category, "value") else str(category or "")


def evidence_grade_for(rec: dict) -> str:
    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    return _EVIDENCE_GRADE.get((tier, level), "B" if tier == EvidenceTier.EMERGING.value else "C+")


def _pathway_activation_index(pathway_activations: list[dict]) -> dict[str, dict]:
    return {p["pathway_code"]: p for p in pathway_activations if (p.get("activation_score") or 0) > 0}


def _intervention_pathway_codes(name: str, intervention_pathways: dict[str, list[str]]) -> list[str]:
    return list(intervention_pathways.get(name, []) or [])


def intervention_network_metrics(
    rec: dict,
    intervention_pathways: dict[str, list[str]],
    pathway_index: dict[str, dict],
    abnormal_names: set[str],
) -> dict:
    """Pathways hit on implicated biology, biomarkers explained, and biology-weighted score."""
    name = rec.get("intervention_name", "")
    codes = _intervention_pathway_codes(name, intervention_pathways)
    implicated_hits = [code for code in codes if code in pathway_index]
    pathways_hit = len(implicated_hits)

    biomarkers_explained: set[str] = set()
    biology_weight = 0.0
    for code in implicated_hits:
        activation = pathway_index[code]
        biology_weight += float(activation.get("activation_score") or 0.0)
        for biomarker in activation.get("contributing_biomarkers") or []:
            if biomarker in abnormal_names:
                biomarkers_explained.add(biomarker)

    active_pathway_count = max(len(pathway_index), 1)
    abnormal_count = max(len(abnormal_names), 1)

    return {
        "pathways_hit": pathways_hit,
        "biomarkers_explained": len(biomarkers_explained),
        "biomarkers_explained_names": sorted(biomarkers_explained),
        "biology_weight": round(biology_weight, 4),
        "pathway_coverage": round(pathways_hit / active_pathway_count, 4),
        "biomarker_coverage": round(len(biomarkers_explained) / abnormal_count, 4),
    }


def biology_first_network_score(
    rec: dict,
    intervention_pathways: dict[str, list[str]],
    pathway_index: dict[str, dict],
    abnormal_names: set[str],
    *,
    display_intent: str | None = None,
) -> float:
    """Rank interventions by implicated biology, not popularity alone."""
    metrics = intervention_network_metrics(rec, intervention_pathways, pathway_index, abnormal_names)
    intent = display_intent or classify_display_intent(rec, abnormal_names)

    tier = _tier_value(rec.get("evidence_tier"))
    level = _level_value(rec.get("evidence_level"))
    human_evidence = {
        (EvidenceTier.ESTABLISHED.value, EvidenceLevel.HIGH.value): 1.0,
        (EvidenceTier.ESTABLISHED.value, EvidenceLevel.MODERATE.value): 0.9,
        (EvidenceTier.EMERGING.value, EvidenceLevel.HIGH.value): 0.75,
        (EvidenceTier.EMERGING.value, EvidenceLevel.MODERATE.value): 0.65,
    }.get((tier, level), 0.35 if tier == EvidenceTier.EMERGING.value else 0.2)

    safety = _SAFETY_BONUS.get(str(rec.get("safety_risk") or "low").lower(), 0.5)
    intent_boost = 0.08 if intent == DisplayIntent.PRIMARY.value else 0.0

    dominant_pathway_confidence = 0.0
    if pathway_index and metrics["pathways_hit"]:
        hit_scores = [
            float(pathway_index[code].get("activation_score") or 0.0)
            for code in _intervention_pathway_codes(rec.get("intervention_name", ""), intervention_pathways)
            if code in pathway_index
        ]
        dominant_pathway_confidence = max(hit_scores) if hit_scores else 0.0

    score = (
        metrics["biology_weight"] * 38.0
        + dominant_pathway_confidence * 18.0
        + metrics["pathway_coverage"] * 16.0
        + metrics["biomarker_coverage"] * 14.0
        + human_evidence * 10.0
        + safety * 4.0
        + intent_boost
    )
    return round(score, 4)


def _evidence_stars(activation_score: float, biomarker_count: int) -> int:
    stars = 1
    if activation_score >= 0.7:
        stars += 2
    elif activation_score >= 0.4:
        stars += 1
    if biomarker_count >= 2:
        stars += 2
    elif biomarker_count >= 1:
        stars += 1
    return min(5, stars)


def _intervention_class_label(rec: dict) -> str:
    name = rec.get("intervention_name", "")
    category = _category_value(rec.get("category"))
    if "diet" in name.lower() or "Mediterranean" in name or "Portfolio" in name:
        return name
    if category == InterventionCategory.PHYTOCHEMICAL.value and "/" not in name:
        parent_foods = {"Allicin": "Garlic / allicin", "Sulforaphane": "Broccoli / sulforaphane"}
        return parent_foods.get(name, name)
    return _INTERVENTION_CLASS_LABELS.get(category, name)


def _enrich_intervention_row(
    rec: dict,
    intervention_pathways: dict[str, list[str]],
    pathway_index: dict[str, dict],
    abnormal_names: set[str],
) -> dict:
    display_intent = classify_display_intent(rec, abnormal_names)
    metrics = intervention_network_metrics(rec, intervention_pathways, pathway_index, abnormal_names)
    row = dict(rec)
    row["display_intent"] = display_intent
    row["pathways_hit"] = metrics["pathways_hit"]
    row["biomarkers_explained"] = metrics["biomarkers_explained"]
    row["biomarkers_explained_names"] = metrics["biomarkers_explained_names"]
    row["evidence_grade"] = evidence_grade_for(rec)
    row["network_rank_score"] = biology_first_network_score(
        rec,
        intervention_pathways,
        pathway_index,
        abnormal_names,
        display_intent=display_intent,
    )
    row["intervention_class"] = _intervention_class_label(rec)
    return row


def build_biological_hierarchy(
    biomarker_summary: dict,
    biological_systems: list[dict],
    pathway_activations: list[dict],
    recommendations: list[dict],
    intervention_pathways: dict[str, list[str]],
) -> dict:
    """Hierarchical biology-first view for clinician reasoning."""
    abnormal = _abnormal_biomarkers(biomarker_summary)
    abnormal_names = {m["biomarker_name"] for m in abnormal}
    pathway_index = _pathway_activation_index(pathway_activations)
    active_systems = [s for s in biological_systems if (s.get("signal_level") or 0) > 0]

    enriched_recs = [
        _enrich_intervention_row(rec, intervention_pathways, pathway_index, abnormal_names)
        for rec in recommendations
    ]
    enriched_recs.sort(key=lambda r: (-r.get("network_rank_score", 0), r.get("rank", 999)))

    for index, rec in enumerate(enriched_recs, start=1):
        rec["network_rank"] = index

    dominant_pathway: dict | None = None
    if pathway_index:
        top_code = max(pathway_index, key=lambda c: float(pathway_index[c].get("activation_score") or 0.0))
        top = pathway_index[top_code]
        biomarkers = sorted(
            b for b in (top.get("contributing_biomarkers") or []) if b in abnormal_names
        ) or list(top.get("contributing_biomarkers") or [])
        activation_score = float(top.get("activation_score") or 0.0)

        pathway_interventions = [
            r for r in enriched_recs
            if top_code in _intervention_pathway_codes(r.get("intervention_name", ""), intervention_pathways)
            and r.get("display_intent") not in (DisplayIntent.REGULATED.value,)
            and _category_value(r.get("category")) not in REGULATED_CATEGORIES
        ]
        pathway_interventions.sort(key=lambda r: -r.get("network_rank_score", 0))
        suggested_classes: list[str] = []
        seen_labels: set[str] = set()
        for row in pathway_interventions[:12]:
            label = row.get("intervention_class") or row.get("intervention_name", "")
            key = label.lower()
            if key in seen_labels:
                continue
            seen_labels.add(key)
            suggested_classes.append(label)
            if len(suggested_classes) >= 7:
                break

        dominant_pathway = {
            "pathway_code": top_code,
            "pathway_name": top.get("pathway_name") or PATHWAY_DISPLAY_NAMES.get(top_code, top_code),
            "confidence_percent": round(activation_score * 100),
            "evidence_stars": _evidence_stars(activation_score, len(biomarkers)),
            "star_label": "★" * _evidence_stars(activation_score, len(biomarkers)),
            "affected_biomarkers": biomarkers,
            "direction": top.get("direction"),
            "suggested_intervention_classes": suggested_classes,
            "headline": (
                f"{PATHWAY_DISPLAY_NAMES.get(top_code, top.get('pathway_name', top_code))} "
                "appears to be the dominant biological signal in this panel."
            ),
        }

    systems_tree: list[dict] = []
    systems_sorted = sorted(
        biological_systems,
        key=lambda s: (-(s.get("signal_level") or 0), s.get("system_name", "")),
    )
    for system in systems_sorted:
        if (system.get("signal_level") or 0) <= 0:
            continue
        system_pathway_codes = SYSTEM_PATHWAYS.get(system.get("system_code", ""), [])
        pathway_nodes: list[dict] = []
        for code in system_pathway_codes:
            activation = pathway_index.get(code)
            if not activation:
                continue
            pathway_interventions = [
                r for r in enriched_recs
                if code in _intervention_pathway_codes(r.get("intervention_name", ""), intervention_pathways)
            ]
            pathway_interventions.sort(key=lambda r: -r.get("network_rank_score", 0))
            pathway_nodes.append(
                {
                    "pathway_code": code,
                    "pathway_name": activation.get("pathway_name") or PATHWAY_DISPLAY_NAMES.get(code, code),
                    "activation_score": activation.get("activation_score"),
                    "confidence_percent": round(float(activation.get("activation_score") or 0.0) * 100),
                    "direction": activation.get("direction"),
                    "contributing_biomarkers": activation.get("contributing_biomarkers") or [],
                    "intervention_count": len(pathway_interventions),
                    "interventions": [
                        {
                            "intervention_name": r.get("intervention_name"),
                            "pathways_hit": r.get("pathways_hit"),
                            "biomarkers_explained": r.get("biomarkers_explained"),
                            "evidence_grade": r.get("evidence_grade"),
                            "display_intent": r.get("display_intent"),
                            "network_rank": r.get("network_rank"),
                            "category": r.get("category"),
                        }
                        for r in pathway_interventions[:15]
                    ],
                }
            )
        pathway_nodes.sort(key=lambda p: -(p.get("activation_score") or 0.0))
        systems_tree.append(
            {
                "system_code": system.get("system_code"),
                "system_name": system.get("system_name") or SYSTEM_NAMES.get(system.get("system_code", ""), ""),
                "signal_level": system.get("signal_level"),
                "signal_label": system.get("signal_label"),
                "confidence": system.get("confidence"),
                "drivers": system.get("drivers") or [],
                "pathways": pathway_nodes,
            }
        )

    network_table = [
        {
            "intervention_name": r.get("intervention_name"),
            "pathways_hit": r.get("pathways_hit"),
            "biomarkers_explained": r.get("biomarkers_explained"),
            "evidence_grade": r.get("evidence_grade"),
            "network_rank": r.get("network_rank"),
            "display_intent": r.get("display_intent"),
        }
        for r in enriched_recs[:20]
    ]

    return {
        "model": "biology_hierarchy_v1",
        "cascade": {
            "abnormal_biomarkers": len(abnormal),
            "systems_evaluated": len(biological_systems) or 7,
            "systems_with_signal": len(active_systems),
            "pathways_activated": len(pathway_index),
            "interventions_mapped": len(recommendations),
        },
        "abnormal_biomarker_details": [
            {
                "biomarker_name": m["biomarker_name"],
                "status": m.get("status"),
                "value": m.get("value"),
                "unit": m.get("unit"),
            }
            for m in abnormal
        ],
        "dominant_biology": dominant_pathway,
        "systems_tree": systems_tree,
        "network_influence_table": network_table,
        "ranking_priorities": [
            "What biology is most abnormal?",
            "How confident are we in that biological inference?",
            "Which interventions influence the greatest number of implicated pathways?",
            "What has the strongest human evidence?",
            "What has the best safety profile?",
        ],
    }