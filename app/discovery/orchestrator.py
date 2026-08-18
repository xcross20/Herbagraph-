"""Turn orchestrator. Case mutates first. Speech only verbalizes the chosen action."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.discovery.actions import NextAction, generate_actions, select_action
from app.discovery.engine import FindingDraft, rebuild_case_state
from app.discovery.ranker import rank_next_actions
from app.discovery.intake import (
    ExtractedFact,
    detect_contradictions,
    extract_facts,
    fact_map,
    facts_to_findings,
    problem_representation,
)
from app.discovery.ai import merge_llm_facts, pick_verbalization
from app.discovery.intent import classify_intent
from app.discovery.literature import wants_evidence as text_wants_evidence
from app.discovery.safety import (
    assess_safety,
    extract_safety_findings,
    findings_from_fact_map,
    safety_findings_to_facts,
)


_PATTERN_UNKNOWNS = (
    "laterality",
    "distribution",
    "weakness",
    "temperature sensation",
    "emg testing",
)
_GI_UNKNOWNS = (
    "pain_location",
    "episode_duration",
    "meal_relation",
    "nausea",
)


@dataclass
class TurnResult:
    intents: list[str]
    safety_status: str
    stage: str
    new_findings: list[FindingDraft]
    contradictions: list[str]
    problem_representation: str
    unknowns: list[str]
    hypotheses: list[str]
    action: NextAction
    message: str
    interaction: dict | None
    what_changed: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    llm_used: bool = False
    critic: str = "Investigation relevance is not a diagnosis."
    safety: dict = field(default_factory=dict)
    discovery_can_continue: bool = True
    clinical_followup_needed: bool = False
    safety_override: bool = False
    guide_plan: dict | None = None
    control: dict | None = None

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["new_findings"] = [asdict(item) for item in self.new_findings]
        payload["action"] = asdict(self.action)
        return payload


def _stage(safety_status: str, facts: dict[str, str], action: NextAction, turn_count: int) -> str:
    if safety_status in {"S4", "S3", "urgent"}:
        return "safety_triage"
    if action.type in {"show_safety_message", "advise_prompt_evaluation"}:
        return "safety_triage"
    if safety_status == "S1":
        return "safety_triage"
    if "laterality" not in facts:
        return "opening"
    if action.type == "clarify":
        return "adaptive_questioning"
    if action.type == "request_record":
        return "evidence_collection"
    if action.type == "retrieve_evidence":
        return "evidence_collection"
    if action.type == "show_investigation_map":
        return "investigation_map"
    if action.type == "transition_to_labs":
        return "evidence_collection"
    if action.type == "recommend_investigation":
        return "next_best_investigation"
    if action.type == "ask_question" and action.question_id and action.question_id.startswith("q_") and "safety" in (action.question_id or ""):
        return "safety_triage"
    if turn_count <= 1:
        return "opening"
    return "adaptive_questioning"


def _unknowns(facts: dict[str, str]) -> list[str]:
    from app.discovery.intake import is_abdominal_case

    keys = _GI_UNKNOWNS if is_abdominal_case(facts) else _PATTERN_UNKNOWNS
    missing: list[str] = []
    for key in keys:
        value = facts.get(key)
        if value is None or value == "unknown":
            missing.append(key)
    return missing


def _usefulness_synthesis(control, facts: dict[str, str], mode: str) -> str:
    del mode
    paused = [code.replace("_", " ") for code, status in control.focus.items() if status == "paused_by_user"]
    active = [code.replace("_", " ") for code, status in control.focus.items() if status == "active"]
    attribution = facts.get("patient_interpretation") or "inflammatory foods"
    paused_line = f" I am not pursuing {', '.join(paused)} unless you resume it." if paused else ""
    return (
        f"Here is a bounded interim view of the active concerns ({', '.join(active) or 'the current symptoms'})."
        f"{paused_line} "
        "Facial heat and right-upper discomfort may or may not share a cause; timing together is not proof. "
        f"“{attribution}” stays your description, not a confirmed mechanism. "
        "Without verified labs I will not interpret numbers. Next useful step is a structured episode log "
        "or a clinician-ready brief — not another intake question. This is not a diagnosis."
    )


def _compose(
    action: NextAction,
    *,
    audience: str,
    facts: dict[str, str],
    prior_facts: dict[str, str],
    contradictions: list[str],
) -> str:
    if action.type == "show_safety_message":
        return (
            "Based on what you've shared so far, this needs urgent in-person evaluation "
            "rather than more Discovery questions. This is not a diagnosis."
        )
    if action.type == "no_candidate":
        return (
            "There is no remaining eligible investigation candidate. "
            "I will not invent a next test. This is not a diagnosis."
        )
    if action.type == "advise_prompt_evaluation":
        return (
            "Based on what you've shared so far, prompt in-person assessment would be the safer next step. "
            "This is not a diagnosis."
        )
    if action.type == "clarify" and contradictions:
        topic = contradictions[0]
        prior = prior_facts.get(topic, facts.get(topic, "a different pattern"))
        return (
            f"Earlier I understood {topic} as {prior.replace('_', ' ')}, but this message does not match. "
            "Is it usually both, with one side worse, or did the pattern change over time? "
            "This is not a diagnosis."
        )
    if action.type == "ask_question" and action.question_id == "q_laterality":
        if audience == "clinician":
            return (
                "I can organize this as an investigation, not a diagnosis. "
                "The first useful discriminator is laterality. "
                f"{action.prompt}"
            )
        return (
            "Thank you for telling me that — I can help organize it into an investigation, not a diagnosis. "
            "First I want to understand the pattern itself. "
            f"{action.prompt}"
        )
    if action.prompt:
        return action.prompt
    return "I have an update on the Case, but I will not write a diagnosis."


def _critic(message: str) -> str:
    banned = ("you have small-fiber", "you have neuropathy", "this confirms", "this strongly suggests")
    lowered = message.lower()
    if any(phrase in lowered for phrase in banned):
        return "blocked"
    return "ok"


def orchestrate(
    text: str,
    *,
    prior_facts: dict[str, str],
    asked: list[str],
    answered: set[str],
    current_closes: str | None = None,
    concern: str | None = None,
    audience: str = "consumer",
    turn_count: int = 0,
    llm_fact_rows: list | None = None,
    llm_message: str | None = None,
    guide_actions: list | None = None,
    wants_evidence: bool | None = None,
    persisted_gaps: list[dict] | None = None,
    control_state: dict | None = None,
) -> TurnResult:
    intents = classify_intent(text, current_question_closes=current_closes)
    prior_safety = findings_from_fact_map(prior_facts)
    safety_findings = extract_safety_findings(text, prior_safety, current_closes=current_closes)
    safety = assess_safety(
        safety_findings,
        asked=set(asked),
        prior_state=prior_facts.get("safety_state"),
        new_text=text,
    )
    incoming = extract_facts(text, current_question_closes=current_closes)
    have = {item.name for item in incoming}
    for item in safety_findings_to_facts(safety_findings):
        if item.name not in have:
            incoming.append(item)
            have.add(item.name)
    incoming.append(ExtractedFact(name="safety_state", value=safety.state, kind="assessment"))
    if llm_fact_rows:
        incoming = merge_llm_facts(incoming, llm_fact_rows, allow_open=True)
    if "uncertainty" in intents and current_closes:
        incoming = [
            *incoming,
            ExtractedFact(name=current_closes, value="unknown", kind="assessment"),
        ]
        answered = set(answered) | {current_closes}

    contradictions = detect_contradictions(prior_facts, incoming)
    merged = dict(prior_facts)
    for fact in incoming:
        merged[fact.name] = fact.value

    family_blob = " ".join(
        part
        for part in (
            concern or text,
            merged.get("nausea"),
            merged.get("fatty_food"),
            merged.get("abdominal_pain"),
            merged.get("patient_interpretation"),
            merged.get("location"),
        )
        if part
    )
    snapshot = rebuild_case_state(family_blob, [], {})
    hypo_labels = [item.label for item in snapshot.hypotheses]
    candidates = generate_actions(
        facts=merged,
        asked=set(asked),
        answered=set(answered),
        contradictions=contradictions,
        safety_status=safety.state,
        hypotheses=snapshot.hypotheses,
        turn_count=turn_count,
        wants_evidence=bool(wants_evidence) or text_wants_evidence(text),
        safety=safety,
        guide_actions=guide_actions,
    )
    from app.discovery.actions import QUESTIONS
    from app.discovery.usefulness import (
        ControlState,
        apply_control,
        decide_response_mode,
        filter_paused_questions,
        slot_is_answered,
        usefulness_governor_enabled,
    )

    control = apply_control(ControlState.from_dict(control_state), text, merged)
    if usefulness_governor_enabled():
        kept = []
        for candidate in candidates:
            closes = next((item.closes for item in QUESTIONS if item.code == candidate.question_id), None)
            if slot_is_answered(control, closes):
                continue
            if filter_paused_questions(candidate.type, candidate.question_id, candidate.prompt, control):
                continue
            kept.append(candidate)
        candidates = kept
    action = select_action(candidates)
    coverage_by_code = {
        getattr(item, "code", ""): float(getattr(item, "investigation_coverage", 0.0) or 0.0)
        for item in snapshot.hypotheses
    }
    _COST = {
        "request_record": 0.55,
        "transition_to_labs": 0.55,
        "retrieve_evidence": 0.25,
        "ask_question": 0.12,
        "clarify": 0.18,
    }
    from app.discovery.evidence_graph import gaps_from_hypotheses

    if persisted_gaps is not None:
        gaps = [dict(item) for item in persisted_gaps]
    else:
        gaps = gaps_from_hypotheses(snapshot.hypotheses)
    for candidate in candidates:
        extras = candidate.extras or {}
        branch = extras.get("branch") or extras.get("branch_code")
        coverage = coverage_by_code.get(branch or "", 0.0)
        asked_already = bool(
            candidate.question_id and (candidate.question_id in asked or candidate.question_id in answered)
        )
        gaps.append(
            {
                "code": candidate.question_id or candidate.type,
                "label": candidate.prompt or candidate.objective,
                "branch_code": branch,
                "action_type": candidate.type,
                "information_value": float(candidate.score or 0.0),
                "coverage_gain": max(0.0, 1.0 - coverage) if branch else float(candidate.score or 0.0),
                "redundancy": 1.0 if asked_already else float(extras.get("redundancy") or 0.0),
                "cost": float(extras.get("cost") or _COST.get(candidate.type, 0.2)),
                "burden": float(extras.get("burden") or _COST.get(candidate.type, 0.2)),
                "explanation": candidate.objective,
                "candidate": candidate,
                "commerce_boosted": bool(extras.get("commerce_boosted")),
                "contraindicated": bool(extras.get("contraindicated")),
                "non_addressing": bool(extras.get("non_addressing")),
            }
        )
    ranked = rank_next_actions(gaps=gaps, safety_level=safety.state)
    if ranked and ranked[0].action_type == "professional_review":
        extras = {**(action.extras or {}), "ranker": ranked[0].version, "explanation": ranked[0].explanation}
        if action.type in {"show_safety_message", "advise_prompt_evaluation"}:
            action.extras = extras
            action.prompt = action.prompt or ranked[0].label
            action.objective = action.objective or ranked[0].label
        else:
            action = NextAction(
                type="advise_prompt_evaluation",
                objective=ranked[0].label,
                prompt=ranked[0].label,
                score=ranked[0].score,
                extras=extras,
            )
    elif ranked and ranked[0].action_type == "no_candidate":
        action = NextAction(
            type="no_candidate",
            objective=ranked[0].label,
            prompt=ranked[0].label,
            score=0.0,
            extras={"ranker": ranked[0].version, "explanation": ranked[0].explanation},
        )
    elif ranked:
        chosen = next((item.get("candidate") for item in gaps if item.get("code") == ranked[0].gap_code), None)
        if chosen is not None:
            action = chosen
        else:
            action = NextAction(
                type=ranked[0].action_type,
                objective=ranked[0].label,
                prompt=ranked[0].label,
                score=ranked[0].score,
                extras={"branch": ranked[0].branch_code, "gap_code": ranked[0].gap_code},
            )
        action.extras = {
            **(action.extras or {}),
            "ranker": ranked[0].version,
            "ranker_score": ranked[0].score,
            "alternatives": list(ranked[0].alternatives),
            **ranked[0].components,
        }
    if usefulness_governor_enabled():
        unanswered_high_value = action.type == "ask_question" and not slot_is_answered(
            control, next((item.closes for item in QUESTIONS if item.code == action.question_id), None)
        )
        mode = decide_response_mode(
            safety_state=safety.state,
            contradictions=contradictions,
            control=control,
            unanswered_high_value=unanswered_high_value,
        )
        if mode in {"INTERIM_SYNTHESIS", "NEXT_STEPS"}:
            action = NextAction(
                type="summarize" if mode == "INTERIM_SYNTHESIS" else "show_investigation_map",
                objective="Bounded interim synthesis of active concerns. This is not a diagnosis.",
                prompt=_usefulness_synthesis(control, merged, mode),
                score=0.94,
                extras={"response_mode": mode, "paused": [code for code, status in control.focus.items() if status == "paused_by_user"]},
            )
        else:
            action.extras = {**(action.extras or {}), "response_mode": mode}
    if safety.state in {"S3", "S4"}:
        message = safety.message or _compose(
            action,
            audience=audience,
            facts=merged,
            prior_facts=prior_facts,
            contradictions=contradictions,
        )
    else:
        message = _compose(
            action,
            audience=audience,
            facts=merged,
            prior_facts=prior_facts,
            contradictions=contradictions,
        )
        if safety.state == "S1" and safety.preface and safety.preface not in message:
            message = f"{safety.preface} {message}".strip()
    if safety.state != "S4":
        message = pick_verbalization(message, llm_message)
    if _critic(message) == "blocked":
        message = "I updated the Case. I will not write a diagnosis. " + (action.prompt or "")

    changed = [f"{item.name}={item.value}" for item in incoming]
    if contradictions:
        changed.append("contradiction:" + ",".join(contradictions))

    return TurnResult(
        intents=intents,
        safety_status=safety.state,
        stage=_stage(safety.state, merged, action, turn_count),
        new_findings=facts_to_findings(incoming),
        contradictions=contradictions,
        problem_representation=problem_representation(merged),
        unknowns=_unknowns(merged),
        hypotheses=hypo_labels,
        action=action,
        message=message.strip(),
        interaction=action.interaction,
        what_changed=changed,
        llm_used=bool(llm_fact_rows or llm_message),
        safety=safety.as_dict(),
        discovery_can_continue=safety.discovery_can_continue,
        clinical_followup_needed=safety.clinical_followup_needed,
        safety_override=safety.override,
        critic=safety.critic if safety.state in {"S3", "S4"} else "Investigation relevance is not a diagnosis.",
        control=control.as_dict() if control is not None else None,
    )


def facts_from_findings(findings: list) -> dict[str, str]:
    drafts = [
        item
        if isinstance(item, FindingDraft)
        else FindingDraft(
            kind=getattr(getattr(item, "kind", "symptom"), "value", getattr(item, "kind", "symptom")),
            name=getattr(item, "name", ""),
            value=getattr(item, "value", None),
            status=None,
            branch=None,
            source="intake",
        )
        for item in findings
    ]
    return fact_map(drafts)
