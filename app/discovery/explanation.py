"""Canonical investigation explanation view. Ask and the panel share this model."""

from __future__ import annotations

from app.discovery.claim_cards import cards_for_next_steps
from app.discovery.modalities import map_for
from app.discovery.next_evidence import plan_next_evidence
from app.discovery.usefulness import ControlState

FAMILY_CONCERN = {
    "small_fiber_dysfunction": "burning_feet",
    "b12_functional_gap": "burning_feet",
    "glucose_dysregulation": "burning_feet",
    "biliary_colic_pattern": "ruq_discomfort",
    "gastric_dyspeptic_pattern": "ruq_discomfort",
    "reflux_pattern": "ruq_discomfort",
}

FAMILY_RELATION = {
    "small_fiber_dysfunction": "dysfunction_confirmation",
    "b12_functional_gap": "contributor_evaluation",
    "glucose_dysregulation": "contributor_evaluation",
    "biliary_colic_pattern": "dysfunction_confirmation",
    "gastric_dyspeptic_pattern": "contributor_evaluation",
    "reflux_pattern": "contributor_evaluation",
}

COVERAGE_GROUP = {
    "directly_assesses": "characterizes_dysfunction",
    "partially_assesses": "characterizes_dysfunction",
    "does_not_directly_assess": "does_not_address",
}

MODALITY_GROUP = {
    "standard_lab": "evaluates_contributor",
    "functional_lab": "evaluates_contributor",
    "examination": "characterizes_dysfunction",
    "electrophysiology": "characterizes_dysfunction",
    "pathology": "characterizes_dysfunction",
    "imaging": "characterizes_dysfunction",
    "monitoring": "monitors_pattern",
    "record_retrieval": "retrieves_existing",
    "history": "retrieves_existing",
    "patient_generated": "monitors_pattern",
}


def _coverage_group(item: dict, family_id: str) -> str:
    del family_id
    if item.get("coverage") in {"does_not_directly_assess", "does_not_address"}:
        if item.get("modality") in {"standard_lab", "functional_lab"}:
            return "evaluates_contributor"
        return "does_not_address"
    if item.get("modality") in {"standard_lab", "functional_lab"}:
        return "evaluates_contributor"
    return MODALITY_GROUP.get(str(item.get("modality") or ""), COVERAGE_GROUP.get(str(item.get("coverage") or ""), "evaluates_contributor"))


def _fact_rows(facts: dict[str, str]) -> list[dict]:
    rows = []
    for name, value in facts.items():
        if name in {"safety_state"}:
            continue
        rows.append({"name": name, "value": value, "provenance": "patient_reported"})
    return rows[:12]


def build_explanation_view(
    *,
    hypotheses: list,
    facts: dict[str, str],
    control: ControlState | dict | None = None,
    planned: list[dict] | None = None,
    cards: list[dict] | None = None,
    response_mode: str | None = None,
) -> dict:
    state = control if isinstance(control, ControlState) else ControlState.from_dict(control)
    planned = list(planned or plan_next_evidence(state))
    family_ids = []
    for hypo in hypotheses or []:
        code = getattr(hypo, "code", None) or (hypo.get("code") if isinstance(hypo, dict) else None)
        if code:
            family_ids.append(str(code))
    cards = [
        item
        for item in (
            cards
            if cards is not None
            else cards_for_next_steps(family_ids, facts=facts)
        )
        if item.get("accepted") and item.get("eligible_for_case") is not False
    ]
    paused = state.paused_family_ids()
    families = []
    for hypo in hypotheses or []:
        family_id = getattr(hypo, "code", None) or (hypo.get("code") if isinstance(hypo, dict) else None)
        if not family_id:
            continue
        label = getattr(hypo, "label", None) or (hypo.get("label") if isinstance(hypo, dict) else family_id)
        concern = FAMILY_CONCERN.get(str(family_id))
        evaluations = []
        for item in map_for(concern) if concern else []:
            group = _coverage_group(item, str(family_id))
            if group == "does_not_address" and item.get("id") == "bf-emg":
                can_tell = "Whether large-fiber motor or sensory conduction is affected."
                cannot_tell = "Small-fiber density or function. A normal EMG does not close this family."
            elif group == "evaluates_contributor":
                can_tell = "Whether a possible contributor remains unevaluated."
                cannot_tell = "It does not confirm or exclude the suspected sensory dysfunction."
            else:
                can_tell = item.get("why") or "May help assess an open gap."
                cannot_tell = "It does not produce a diagnosis or disease probability."
            evaluations.append(
                {
                    "id": item["id"],
                    "label": item["label"],
                    "modality": item.get("modality"),
                    "coverage": item.get("coverage"),
                    "coverage_relation": group,
                    "can_tell": can_tell,
                    "cannot_tell": cannot_tell,
                    "authorization": "professional" if item.get("modality") in {"examination", "pathology", "electrophysiology"} else "none",
                    "why": item.get("why"),
                }
            )
        family_paused = str(family_id) in paused
        families.append(
            {
                "id": family_id,
                "label": label,
                "relationship": FAMILY_RELATION.get(str(family_id), "contributor_evaluation"),
                "status": "paused_by_user" if family_paused else "active",
                "supporting_facts": _fact_rows(facts),
                "contradictions": [],
                "unknowns": list(getattr(hypo, "missing_markers", None) or (hypo.get("missing_markers") if isinstance(hypo, dict) else []) or [])[:6],
                "rationale": getattr(hypo, "not_a_diagnosis", None)
                or "Open because related findings are present. This is not a diagnosis.",
                "evaluations": [] if family_paused else evaluations,
                "claim_card_ids": [item["source_id"] for item in cards],
                "limitations": ["Investigation relevance is not a diagnosis."],
                "next_action": "Paused by you" if family_paused else "Prepare for clinician",
            }
        )
    ranked = [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "why": item.get("explanation"),
            "alternatives": item.get("alternatives") or [],
        }
        for item in planned[:3]
    ]
    if ranked:
        leading = ranked[0]
        alt = ranked[1]["label"] if len(ranked) > 1 else "the next eligible option"
        leading["why_first"] = (
            f"{leading.get('label')} ranks first because it adds coverage with lower burden than {alt}."
        )
    return {
        "version": "investigation-explanation-v1",
        "response_mode": response_mode,
        "families": families,
        "ranked_actions": ranked,
        "claim_cards": cards,
        "next_action": "Explore evaluation options",
    }


def render_explanation_text(view: dict, *, facts: dict[str, str] | None = None) -> str:
    facts = facts or {}
    families = view.get("families") or []
    labels = ", ".join(item.get("label") or item.get("id") or "a family" for item in families[:3]) or "the open families"
    family_ids = {str(item.get("id") or "") for item in families}
    ruq = bool(family_ids & {"biliary_colic_pattern", "gastric_dyspeptic_pattern", "reflux_pattern"})
    sensory = bool(family_ids & {"small_fiber_dysfunction", "b12_functional_gap", "glucose_dysregulation"})
    b12 = facts.get("prior_labs.b12_last_check") or ""
    b12_line = (
        " I recorded a patient-reported B12 check from last year; I will not ask that again, and a recalled total B12 does not close the branch."
        if b12 and sensory
        else ""
    )
    labs_line = ""
    if sensory:
        labs_line = " Prior routine bloodwork does not itself assess small-fiber function."
    if ruq:
        labs_line += (
            " I am organizing the reported post-meal right-upper discomfort and fat-meal association as investigation targets, "
            "not as a gallbladder diagnosis."
        )
    attribution = facts.get("patient_interpretation") or (
        "inflammatory foods" if any("inflamm" in str(value).lower() for value in facts.values()) else ""
    )
    attr_line = (
        f" “{attribution}” stays your description, not a confirmed mechanism."
        if attribution
        else ""
    )
    actions = view.get("ranked_actions") or []
    action_line = ""
    if actions:
        bits = []
        for item in actions[:3]:
            why = item.get("why_first") or item.get("why") or "may help assess an open gap"
            bits.append(f"{item.get('label')} ({why})")
        action_line = " Ranked next evidence, not a diagnosis: " + "; ".join(bits) + "."
    paused_labels = [item.get("label") or item.get("id") for item in families if item.get("status") == "paused_by_user"]
    pause_line = f" I paused {', '.join(str(item) for item in paused_labels)} and will not keep asking about it." if paused_labels else ""
    cards = [item.get("title") or item.get("source_id") for item in (view.get("claim_cards") or []) if item.get("accepted")]
    cite_line = (
        f" Stored research: {'; '.join(str(item) for item in cards[:2])}."
        if cards
        else " Relevant literature is not yet available for the selected claim. Missing literature stays a limitation, not an invented citation."
    )
    return (
        f"Here is a bounded interim view of {labels}.{b12_line}{labs_line}{attr_line}{pause_line} "
        "These remain possibilities because coverage is incomplete, not because a diagnosis is established. "
        "They may or may not share a cause; timing together is not proof. "
        "Tests that assess a dysfunction are not the same as tests that evaluate a contributor."
        f"{action_line}{cite_line} "
        "I can prepare a clinician-ready brief or a structured tracker. This is not a diagnosis."
    )
