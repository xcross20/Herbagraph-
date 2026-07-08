"""Page-1 clinical summary hero — stitches priorities into one clinician-facing view."""

from __future__ import annotations

from app.models.enums import InterventionCategory
from app.pipeline.report_clinical_priorities import (
    _PROBLEM_LABELS,
    build_confidence_if_added_steps,
    diagnostic_next_steps,
)

_POSITIONING = "AI Clinical Reasoning for Precision Nutrition"

_LEVERAGE_MEDALS = ("🥇", "🥈", "🥉", "4️⃣", "5️⃣")

_CATEGORY_ICON = {
    InterventionCategory.EXERCISE.value: "🏃",
    InterventionCategory.BEHAVIOR.value: "🥗",
    InterventionCategory.FOOD.value: "🥗",
    InterventionCategory.SLEEP.value: "😴",
}


def build_confidence_if_added(
    primary_priority: dict | None,
    measured: set[str],
    *,
    base_confidence_percent: int | None = None,
) -> list[dict]:
    return build_confidence_if_added_steps(primary_priority, measured, base_confidence_percent=base_confidence_percent)


def _hero_leverage_interventions(
    primary: dict | None,
    network_groups: list[dict],
    *,
    limit: int = 5,
) -> list[dict]:
    ordered: list[dict] = []
    seen: set[str] = set()

    if primary:
        for item in primary.get("potential_interventions", []):
            key = (item.get("label") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(item)
            if len(ordered) >= limit:
                break

    if len(ordered) < limit:
        for group in network_groups:
            for item in group.get("interventions", []):
                key = (item.get("intervention_name") or "").lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                ordered.append(
                    {
                        "kind": "intervention",
                        "label": item.get("intervention_name"),
                        "category": item.get("category"),
                        "clinical_tags": item.get("clinical_tags") or [],
                        "evidence_grade": item.get("evidence_grade"),
                    }
                )
                if len(ordered) >= limit:
                    break
            if len(ordered) >= limit:
                break

    medals = _LEVERAGE_MEDALS
    for index, row in enumerate(ordered[:limit]):
        category = row.get("category", "")
        if hasattr(category, "value"):
            category = category.value
        row["medal"] = medals[index] if index < len(medals) else f"{index + 1}."
        row["icon"] = _CATEGORY_ICON.get(str(category).lower(), "💊")
        row["rank"] = index + 1
    return ordered[:limit]


def build_clinical_summary_hero(
    dual_clinical_rankings: dict,
    overall_confidence_assessment: dict | None,
    biomarker_summary: dict,
) -> dict:
    """Single stitched hero for page 1 of the report."""
    measured = {
        m["biomarker_name"] for m in biomarker_summary.get("measured_biomarkers", [])
    }
    priorities = dual_clinical_rankings.get("clinical_priorities") or []
    primary = priorities[0] if priorities else None
    network_groups = dual_clinical_rankings.get("network_leverage_groups") or []

    oca = overall_confidence_assessment or {}
    overall_label = (
        oca.get("confidence_label_upper")
        or oca.get("confidence_label")
        or (primary or {}).get("confidence", "Moderate")
    )
    overall_percent = None
    if oca.get("confidence_numeric") is not None:
        overall_percent = round(float(oca["confidence_numeric"]) * 100)

    spec = _PROBLEM_LABELS.get((primary or {}).get("biomarker_name", ""), {})
    likely = spec.get("problem_label", (primary or {}).get("problem_label", "Primary biological signal"))
    if primary and "deficiency" in likely.lower():
        likely_short = likely.replace(" biology", "").replace(" store depletion", " store depletion")
    else:
        likely_short = likely

    next_tests = (primary or {}).get("diagnostic_next_steps") or diagnostic_next_steps(spec, measured, limit=5)

    confidence_if_added = build_confidence_if_added(
        primary,
        measured,
        base_confidence_percent=overall_percent,
    )
    if confidence_if_added and overall_percent is None:
        overall_percent = confidence_if_added[0]["confidence_percent"]

    leverage = _hero_leverage_interventions(primary, network_groups, limit=5)

    return {
        "model": "clinical_summary_hero_v1",
        "positioning": _POSITIONING,
        "title": "HerbaGraph Clinical Summary",
        "overall_confidence_label": str(overall_label).upper() if overall_label else "MODERATE",
        "overall_confidence_percent": overall_percent,
        "primary_finding": {
            "label": (primary or {}).get("problem_label", "No primary finding"),
            "confidence": (primary or {}).get("confidence", "Moderate"),
            "biomarker_name": (primary or {}).get("biomarker_name"),
            "star_label": (primary or {}).get("star_label"),
        },
        "likely_explanation": likely_short,
        "alternative_explanations": (primary or {}).get("differential_alternatives") or [],
        "diagnostic_note": (primary or {}).get("diagnostic_note"),
        "most_important_next_tests": next_tests,
        "highest_leverage_interventions": leverage,
        "confidence_if_added": confidence_if_added,
        "secondary_priorities": priorities[1:4],
    }


