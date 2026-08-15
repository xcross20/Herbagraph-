"""Turn orchestrator. Case mutates first. Speech only verbalizes the chosen action."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.discovery.actions import NextAction, generate_actions, select_action
from app.discovery.engine import FindingDraft, rebuild_case_state
from app.discovery.intake import (
    ExtractedFact,
    detect_contradictions,
    extract_facts,
    fact_map,
    facts_to_findings,
    problem_representation,
)
from app.discovery.intent import classify_intent
from app.discovery.safety import screen_safety


_PATTERN_UNKNOWNS = (
    "laterality",
    "distribution",
    "weakness",
    "temperature sensation",
    "emg testing",
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
    critic: str = "Investigation relevance is not a diagnosis."

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["new_findings"] = [asdict(item) for item in self.new_findings]
        payload["action"] = asdict(self.action)
        return payload


def _stage(safety_status: str, facts: dict[str, str], action: NextAction, turn_count: int) -> str:
    if safety_status == "urgent":
        return "safety_triage"
    if action.type == "show_safety_message":
        return "safety_triage"
    if "laterality" not in facts:
        return "opening"
    if action.type == "clarify":
        return "adaptive_questioning"
    if action.type == "request_record":
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
    missing: list[str] = []
    for key in _PATTERN_UNKNOWNS:
        value = facts.get(key)
        if value is None or value == "unknown":
            missing.append(key)
    return missing


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
            "This pattern needs urgent in-person evaluation, not more Discovery questions. "
            "New weakness or a sudden change is outside what this workspace can organize. "
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
            "I can help organize this into an investigation. First I want to understand the pattern itself, "
            "because burning in the feet can arise from several different processes. "
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
) -> TurnResult:
    intents = classify_intent(text, current_question_closes=current_closes)
    safety = screen_safety(text)
    incoming = extract_facts(text, current_question_closes=current_closes)
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

    snapshot = rebuild_case_state(concern or text, [], {})
    hypo_labels = [item.label for item in snapshot.hypotheses]
    candidates = generate_actions(
        facts=merged,
        asked=set(asked),
        answered=set(answered),
        contradictions=contradictions,
        safety_status=safety.status,
        hypotheses=snapshot.hypotheses,
        turn_count=turn_count,
    )
    action = select_action(candidates)
    message = safety.message if safety.status == "urgent" else _compose(
        action,
        audience=audience,
        facts=merged,
        prior_facts=prior_facts,
        contradictions=contradictions,
    )
    if _critic(message) == "blocked":
        message = "I updated the Case. I will not write a diagnosis. " + (action.prompt or "")

    changed = [f"{item.name}={item.value}" for item in incoming]
    if contradictions:
        changed.append("contradiction:" + ",".join(contradictions))

    return TurnResult(
        intents=intents,
        safety_status=safety.status,
        stage=_stage(safety.status, merged, action, turn_count),
        new_findings=facts_to_findings(incoming),
        contradictions=contradictions,
        problem_representation=problem_representation(merged),
        unknowns=_unknowns(merged),
        hypotheses=hypo_labels,
        action=action,
        message=message.strip(),
        interaction=action.interaction,
        what_changed=changed,
    )


def facts_from_findings(findings: list) -> dict[str, str]:
    drafts = [
        item
        if isinstance(item, FindingDraft)
        else FindingDraft(
            kind=getattr(item, "kind", "symptom"),
            name=getattr(item, "name", ""),
            value=getattr(item, "value", None),
            status=None,
            branch=None,
            source="intake",
        )
        for item in findings
    ]
    return fact_map(drafts)
