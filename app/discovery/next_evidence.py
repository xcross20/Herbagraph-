"""Issue 58 Slice B + #61: next-evidence planner over multimodal maps."""

from __future__ import annotations

from app.discovery.modalities import map_for, modalities
from app.discovery.ranker import rank_next_actions
from app.discovery.usefulness import FAMILY_CANDIDATE_IDS, FAMILY_TARGETS, ControlState

NON_ADDRESSING = frozenset({"does_not_directly_assess", "does_not_address", "unknown"})


def planner_enabled() -> bool:
    from app.config import get_settings

    return bool(getattr(get_settings(), "next_evidence_planner_v1", False))


def _modality_meta(code: str) -> dict:
    return next((item for item in modalities() if item["code"] == code), {})


def _paused_candidate_ids(control: ControlState) -> set[str]:
    blocked: set[str] = set()
    for family_id in control.paused_family_ids():
        blocked.update(FAMILY_CANDIDATE_IDS.get(family_id) or ())
    return blocked


def _paused_targets(control: ControlState) -> set[str]:
    return {FAMILY_TARGETS[code] for code in control.paused_family_ids() if code in FAMILY_TARGETS}


def candidates_for_control(control: ControlState, *, records_available: bool = False) -> list[dict]:
    rows: list[dict] = []
    blocked_ids = _paused_candidate_ids(control)
    blocked_targets = _paused_targets(control)
    for concern, status in control.focus.items():
        if status == "paused_by_user":
            continue
        if status not in {"active", "background"}:
            continue
        for item in map_for(concern):
            if item.get("id") in blocked_ids or item.get("target") in blocked_targets:
                continue
            coverage = item.get("coverage") or "unknown"
            if coverage in NON_ADDRESSING and item.get("modality") not in {
                "patient_generated",
                "monitoring",
                "record_retrieval",
                "history",
            }:
                continue
            if item.get("modality") == "record_retrieval" and records_available is False:
                # still eligible: retrieving missing records is high value
                pass
            meta = _modality_meta(str(item.get("modality") or ""))
            rows.append(
                {
                    "code": item["id"],
                    "label": item["label"],
                    "branch_code": concern,
                    "action_type": "next_evidence",
                    "modality": item.get("modality"),
                    "target": item.get("target"),
                    "coverage": coverage,
                    "information_value": float(item.get("information_value") or 0.5),
                    "coverage_gain": 0.85 if coverage == "directly_assesses" else 0.55,
                    "cost": float(meta.get("cost") or 0.2),
                    "burden": float(meta.get("burden") or 0.2),
                    "commerce_boosted": False,
                    "explanation": item.get("why") or "May help assess an open gap.",
                    "authorization": meta.get("authorization") or "none",
                }
            )
    return rows


def plan_next_evidence(control: ControlState, *, records_available: bool = False, safety_level: str = "S0") -> list[dict]:
    ranked = rank_next_actions(gaps=candidates_for_control(control, records_available=records_available), safety_level=safety_level)
    planned = []
    for item in ranked[:3]:
        if item.action_type in {"no_candidate", "professional_review"}:
            planned.append(
                {
                    "id": item.gap_code or item.action_type,
                    "label": item.label,
                    "score": item.score,
                    "explanation": item.explanation,
                    "action_type": item.action_type,
                    "alternatives": list(item.alternatives),
                }
            )
            continue
        planned.append(
            {
                "id": item.gap_code,
                "label": item.label,
                "score": item.score,
                "explanation": item.explanation,
                "action_type": item.action_type,
                "branch_code": item.branch_code,
                "components": item.components,
                "alternatives": list(item.alternatives),
            }
        )
    return planned
