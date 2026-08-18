"""Discovery Guide — LLM-led consultation with deterministic validation."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.discovery.actions import NextAction
from app.discovery.ai import (
    critic_allows,
    discovery_llm_ready,
    is_denied_concept,
    merge_llm_facts,
    pick_verbalization,
    try_llm_json,
)
from app.discovery.orchestrator import TurnResult, orchestrate
from app.discovery.prompts import pass_a_system_prompt, pass_b_system_prompt

logger = logging.getLogger(__name__)

GUIDE_ACTION_TYPES = {
    "ASK_QUESTION": "ask_question",
    "ASK_SMALL_GROUP": "ask_question",
    "REFLECT": "summarize",
    "CLARIFY": "clarify",
    "SEARCH_LITERATURE": "retrieve_evidence",
    "REQUEST_RECORD": "request_record",
    "SHOW_INVESTIGATION_MAP": "show_investigation_map",
    "ESCALATE_SAFETY": "show_safety_message",
}

class CandidateFinding(BaseModel):
    concept: str = ""
    type: str = "symptom"
    value: str | None = None
    verification: str = "patient_reported"


class NextActionCandidate(BaseModel):
    type: str = "ASK_QUESTION"
    prompt: str | None = None
    reason: str = ""
    options: list[str] = Field(default_factory=list)


class CandidateInterpretation(BaseModel):
    statement: str = ""
    concept: str | None = None


class CandidateTimelineEvent(BaseModel):
    label: str = ""
    date_text: str | None = None
    relationship: str | None = None
    confidence: float = 0.5


class BranchUpdateCandidate(BaseModel):
    branch_code: str | None = None
    proposed_label: str = ""
    operation: str = "NO_CHANGE"
    rationale: str = ""


class ToolRequest(BaseModel):
    tool: str = ""
    query: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class DiscoveryTurnPlan(BaseModel):
    user_intents: list[str] = Field(default_factory=list)
    reported_facts: list[CandidateFinding] = Field(default_factory=list)
    reported_findings: list[CandidateFinding] = Field(default_factory=list)
    patient_interpretations: list[str] = Field(default_factory=list)
    timeline_updates: list[str] = Field(default_factory=list)
    timeline_events: list[CandidateTimelineEvent] = Field(default_factory=list)
    prior_workup: list[dict[str, Any]] = Field(default_factory=list)
    prior_workup_updates: list[dict[str, Any]] = Field(default_factory=list)
    branch_updates: list[BranchUpdateCandidate] = Field(default_factory=list)
    evidence_gap_updates: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    corrections: list[dict[str, Any]] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    uncertainty_updates: list[str] = Field(default_factory=list)
    literature_queries: list[str] = Field(default_factory=list)
    tool_requests: list[ToolRequest] = Field(default_factory=list)
    action_candidates: list[NextActionCandidate] = Field(default_factory=list)
    recommended_next_action: NextActionCandidate | None = None
    problem_representation: str = ""
    missing_dimensions: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    wants_evidence: bool = False


_TEXT_KEYS = (
    "text",
    "value",
    "concept",
    "summary",
    "description",
    "interpretation",
    "event",
    "note",
    "prompt",
    "question",
    "name",
    "label",
)


def _as_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    return [raw]


def _as_text(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, (int, float)) and not isinstance(item, bool):
        return str(item)
    if isinstance(item, dict):
        parts: list[str] = []
        seen: set[str] = set()
        for key in _TEXT_KEYS:
            val = item.get(key)
            if isinstance(val, str) and val.strip() and val.strip().lower() not in seen:
                seen.add(val.strip().lower())
                parts.append(val.strip())
        if parts:
            return " — ".join(parts)
        leftover = [
            str(val).strip()
            for key, val in item.items()
            if key not in {"type", "verification", "kind"} and isinstance(val, str) and val.strip()
        ]
        return " — ".join(leftover)
    if isinstance(item, list):
        return "; ".join(part for part in (_as_text(child) for child in item) if part)
    return ""


def _as_text_list(raw: Any) -> list[str]:
    return [text for text in (_as_text(item) for item in _as_list(raw)) if text]


def _as_finding(item: Any) -> dict[str, str] | None:
    if isinstance(item, str):
        concept = item.strip()
        if not concept:
            return None
        return {"concept": concept, "type": "context", "value": "reported"}
    if not isinstance(item, dict):
        text = _as_text(item)
        if not text:
            return None
        return {"concept": text, "type": "context", "value": "reported"}
    concept = _as_text(item.get("concept") or item.get("name") or item.get("text") or "")
    if not concept:
        return None
    value = item.get("value")
    value_text = value.strip() if isinstance(value, str) and value.strip() else _as_text(value)
    kind = str(item.get("type") or item.get("kind") or "symptom")
    return {"concept": concept, "type": kind, "value": value_text or "reported"}


def _as_workup(item: Any) -> dict[str, str] | None:
    if isinstance(item, str):
        test = item.strip()
        return {"test": test, "result": "mentioned"} if test else None
    if not isinstance(item, dict):
        test = _as_text(item)
        return {"test": test, "result": "mentioned"} if test else None
    test = _as_text(item.get("test") or item.get("name") or item.get("concept") or "")
    if not test:
        return None
    result = _as_text(item.get("result") or item.get("value") or "mentioned")
    return {"test": test, "result": result or "mentioned"}


def _as_action(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        prompt = item.strip()
        return {"type": "ASK_QUESTION", "prompt": prompt} if prompt else None
    if not isinstance(item, dict):
        return None
    action_type = str(item.get("type") or "ASK_QUESTION")
    prompt = _as_text(item.get("prompt") or item.get("text") or "")
    options = _as_text_list(item.get("options"))
    reason = _as_text(item.get("reason") or "")
    if not prompt and action_type not in {"REFLECT", "SHOW_INVESTIGATION_MAP", "ESCALATE_SAFETY"}:
        return None
    return {"type": action_type, "prompt": prompt or None, "reason": reason, "options": options}


def coerce_plan_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten messy LLM shapes before Pydantic sees them."""
    data = dict(raw or {})
    data["reported_facts"] = [row for item in _as_list(data.get("reported_facts")) if (row := _as_finding(item))]
    for key in (
        "user_intents",
        "patient_interpretations",
        "timeline_updates",
        "contradictions",
        "safety_flags",
        "uncertainty_updates",
        "literature_queries",
        "missing_dimensions",
    ):
        data[key] = _as_text_list(data.get(key))
    data["prior_workup"] = [row for item in _as_list(data.get("prior_workup")) if (row := _as_workup(item))]
    data["action_candidates"] = [
        row for item in _as_list(data.get("action_candidates")) if (row := _as_action(item))
    ]
    rec = data.get("recommended_next_action")
    data["recommended_next_action"] = _as_action(rec) if rec else None
    events: list[dict[str, Any]] = []
    for item in _as_list(data.get("timeline_events")):
        if isinstance(item, dict) and (item.get("label") or item.get("event")):
            events.append(
                {
                    "label": _as_text(item.get("label") or item.get("event")),
                    "date_text": _as_text(item.get("date_text") or item.get("date")) or None,
                    "relationship": _as_text(item.get("relationship")) or None,
                }
            )
        elif _as_text(item):
            events.append({"label": _as_text(item)})
    data["timeline_events"] = events
    branches: list[dict[str, Any]] = []
    for item in _as_list(data.get("branch_updates")):
        if isinstance(item, dict) and (item.get("proposed_label") or item.get("branch_code")):
            branches.append(
                {
                    "branch_code": item.get("branch_code"),
                    "proposed_label": _as_text(item.get("proposed_label") or item.get("label")),
                    "operation": str(item.get("operation") or "NO_CHANGE"),
                    "rationale": _as_text(item.get("rationale")),
                }
            )
    data["branch_updates"] = branches
    tools: list[dict[str, Any]] = []
    for item in _as_list(data.get("tool_requests")):
        if isinstance(item, dict) and item.get("tool"):
            tools.append(
                {
                    "tool": str(item.get("tool")),
                    "query": item.get("query") if isinstance(item.get("query"), dict) else {},
                    "reason": _as_text(item.get("reason")),
                }
            )
    data["tool_requests"] = tools
    data["prior_workup_updates"] = [
        row for item in _as_list(data.get("prior_workup_updates")) if (row := _as_workup(item))
    ]
    data["corrections"] = [item for item in _as_list(data.get("corrections")) if isinstance(item, dict)]
    data["evidence_gap_updates"] = [
        item for item in _as_list(data.get("evidence_gap_updates")) if isinstance(item, dict)
    ]
    if data.get("problem_representation") is not None and not isinstance(data.get("problem_representation"), str):
        data["problem_representation"] = _as_text(data.get("problem_representation"))
    if data.get("reasoning_summary") is not None and not isinstance(data.get("reasoning_summary"), str):
        data["reasoning_summary"] = _as_text(data.get("reasoning_summary"))
    return data


def validate_plan(raw: dict[str, Any] | None) -> DiscoveryTurnPlan:
    payload = coerce_plan_payload(raw)
    try:
        plan = DiscoveryTurnPlan.model_validate(payload)
    except ValidationError:
        logger.info("discovery plan still invalid after coerce; keeping flattened strings")
        facts: list[CandidateFinding] = []
        for item in payload.get("reported_facts") or []:
            try:
                facts.append(CandidateFinding.model_validate(item))
            except ValidationError:
                continue
        plan = DiscoveryTurnPlan.model_construct(
            reported_facts=facts,
            patient_interpretations=list(payload.get("patient_interpretations") or []),
            timeline_updates=list(payload.get("timeline_updates") or []),
            prior_workup=list(payload.get("prior_workup") or []),
            uncertainty_updates=list(payload.get("uncertainty_updates") or []),
            literature_queries=list(payload.get("literature_queries") or []),
            problem_representation=str(payload.get("problem_representation") or ""),
        )
    kept: list[CandidateFinding] = []
    for item in plan.reported_facts:
        concept = (item.concept or "").strip()
        if not concept or is_denied_concept(concept):
            continue
        kind = item.type if item.type in {"symptom", "context", "assessment"} else "symptom"
        kept.append(
            CandidateFinding(
                concept=concept[:180],
                type=kind,
                value=(item.value or "reported")[:400],
                verification="patient_reported",
            )
        )
    plan.reported_facts = kept[:32]
    plan.patient_interpretations = [
        item.strip()[:400] for item in plan.patient_interpretations if item and not is_denied_concept(item)
    ][:16]
    plan.timeline_updates = [item.strip()[:400] for item in plan.timeline_updates if item][:16]
    workup: list[dict[str, Any]] = []
    for row in plan.prior_workup:
        test = str(row.get("test") or "").strip()
        if not test:
            continue
        workup.append(
            {
                "test": test[:160],
                "result": str(row.get("result") or "mentioned")[:240],
                "verification": "patient_reported",
            }
        )
    plan.prior_workup = workup[:12]
    plan.action_candidates = [
        item
        for item in plan.action_candidates
        if item.type in GUIDE_ACTION_TYPES and (item.prompt or item.type in {"REFLECT", "SHOW_INVESTIGATION_MAP", "ESCALATE_SAFETY"})
    ][:7]
    if plan.recommended_next_action and plan.recommended_next_action.type not in GUIDE_ACTION_TYPES:
        plan.recommended_next_action = None
    if plan.problem_representation and (
        is_denied_concept(plan.problem_representation) or not critic_allows(plan.problem_representation)
    ):
        plan.problem_representation = ""
    plan.uncertainty_updates = [item.strip()[:240] for item in plan.uncertainty_updates if item][:12]
    if not plan.reported_findings:
        plan.reported_findings = list(plan.reported_facts)
    if not plan.timeline_events:
        plan.timeline_events = [CandidateTimelineEvent(label=item) for item in plan.timeline_updates]
    if not plan.prior_workup_updates:
        plan.prior_workup_updates = list(plan.prior_workup)
    if not plan.unresolved_dimensions:
        plan.unresolved_dimensions = list(plan.missing_dimensions)
    return plan


def citation_lines(citations: list[dict] | None) -> list[str]:
    """Titles only for retrieved, digit-only PMIDs. Invented ids never appear."""
    lines: list[str] = []
    for item in citations or []:
        pmid = str(item.get("pmid") or "")
        title = str(item.get("title") or "").strip()
        if pmid.isdigit() and title:
            lines.append(f"{title} (PMID {pmid})")
        if len(lines) == 3:
            break
    return lines


def _next_repeatable(stem: str, used: set[str]) -> str:
    if stem not in used:
        used.add(stem)
        return stem
    index = 2
    while f"{stem}_{index}" in used:
        index += 1
    keyed = f"{stem}_{index}"
    used.add(keyed)
    return keyed


def plan_to_fact_rows(plan: DiscoveryTurnPlan) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    used: set[str] = set()
    for item in plan.reported_facts:
        name = item.concept.lower()
        if name in used:
            continue
        used.add(name)
        rows.append({"name": name, "value": item.value or "reported", "kind": item.type})
    for interp in plan.patient_interpretations:
        rows.append({"name": _next_repeatable("patient_interpretation", used), "value": interp, "kind": "context"})
    for event in plan.timeline_updates:
        rows.append({"name": _next_repeatable("timeline", used), "value": event, "kind": "context"})
    for row in plan.prior_workup:
        rows.append(
            {
                "name": _next_repeatable("prior_workup", used),
                "value": f"{row['test']}: {row['result']} (patient_reported)",
                "kind": "assessment",
            }
        )
    return rows


def guide_candidates_to_actions(plan: DiscoveryTurnPlan) -> list[NextAction]:
    ranked: list[NextAction] = []
    recommended = plan.recommended_next_action
    rec_prompt = (recommended.prompt or "") if recommended else ""
    for index, item in enumerate(plan.action_candidates or []):
        mapped = GUIDE_ACTION_TYPES.get(item.type)
        if not mapped:
            continue
        score = 0.83 - (index * 0.01)
        if recommended and item.prompt == rec_prompt and item.type == recommended.type:
            score = 0.86
        options = [opt for opt in item.options if opt][:6]
        interaction = {"type": "single_select", "options": options} if options else None
        ranked.append(
            NextAction(
                type=mapped,
                objective=item.reason or "Case-specific next step from Discovery Guide.",
                question_id=f"q_guide_{index}" if mapped == "ask_question" else None,
                prompt=item.prompt,
                interaction=interaction,
                score=score,
            )
        )
    if recommended and not ranked:
        mapped = GUIDE_ACTION_TYPES.get(recommended.type)
        if mapped:
            ranked.append(
                NextAction(
                    type=mapped,
                    objective=recommended.reason or "Case-specific next step from Discovery Guide.",
                    question_id="q_guide_0" if mapped == "ask_question" else None,
                    prompt=recommended.prompt,
                    score=0.86,
                )
            )
    return ranked


async def _emit(on_phase: Callable[..., Any] | None, phase: str, label: str) -> None:
    if on_phase is None:
        return
    maybe = on_phase(phase, label)
    if inspect.isawaitable(maybe):
        await maybe


class DiscoveryGuide:
    """Longitudinal conversational health investigation agent."""

    async def plan_turn(self, text: str, *, context: dict[str, Any]) -> DiscoveryTurnPlan | None:
        if not discovery_llm_ready():
            return None
        data = await try_llm_json(
            pass_a_system_prompt(),
            (
                f"user_turn:\n{text}\n\n"
                f"presenting_concern: {context.get('concern') or ''}\n"
                f"known_facts: {context.get('prior_facts') or {}}\n"
                f"recent_turns: {context.get('recent_turns') or []}\n"
                f"problem_representation: {context.get('problem') or ''}\n"
                f"last_visit: {context.get('last_visit') or {}}\n"
                f"person_context: {context.get('person') or {}}\n"
                "Parse the entire user_turn. Keep odd, incomplete, and unusual threads as separate "
                "facts, timeline items, or interpretations. Do not collapse a complex story. "
                "patient_interpretations and timeline_updates are arrays of strings, not objects. "
                "If they just answered a question, do not recommend that question again. "
                "When safety is not urgent, recommend one discriminator among competing investigation "
                "branches (for example location, meal timing, episode length) — not a diagnosis. "
                "Integrate person_context. Do not invent labs or citations."
            ),
            max_tokens=2500,
        )
        if not data:
            return None
        return validate_plan(data)

    async def compose_turn(
        self,
        *,
        action: NextAction,
        safety_state: str,
        problem: str,
        audience: str,
        plan: DiscoveryTurnPlan | None,
        person: dict | None = None,
        citations: list[dict] | None = None,
        last_user_turn: str = "",
    ) -> str | None:
        if not discovery_llm_ready():
            return None
        cite_lines = citation_lines(citations)
        data = await try_llm_json(
            pass_b_system_prompt(),
            (
                f"audience={audience}\n"
                f"safety_state={safety_state}\n"
                f"action={action.type}\n"
                f"required_question={action.prompt or ''}\n"
                f"last_user_turn={last_user_turn}\n"
                f"problem={problem}\n"
                f"unknowns={list((plan.missing_dimensions if plan else [])[:10])}\n"
                f"reported_facts={[item.concept for item in (plan.reported_facts if plan else [])][:20]}\n"
                f"interpretations={(plan.patient_interpretations if plan else [])[:12]}\n"
                f"timeline={(plan.timeline_updates if plan else [])[:12]}\n"
                f"person_context={person or {}}\n"
                f"retrieved_citations={cite_lines}\n"
                "Start from last_user_turn. Do not reuse an earlier opener. "
                "A patient theory (gallbladder, etc.) is not a confirmed problem — say they wondered about it, "
                "do not say they have been experiencing that disease. "
                "Do not ask a question they already answered. "
                "If safety_state is S0 or S2, ask one discriminator that splits open investigation branches. "
                "Never diagnose. Mention a citation only if retrieved_citations is non-empty."
            ),
        )
        if not data:
            return None
        message = data.get("message")
        return str(message) if message else None

    async def process_turn(
        self,
        text: str,
        *,
        prior_facts: dict[str, str],
        asked: list[str],
        answered: set[str],
        current_closes: str | None = None,
        concern: str | None = None,
        audience: str = "consumer",
        turn_count: int = 0,
        recent_turns: list[str] | None = None,
        problem: str | None = None,
        plan: DiscoveryTurnPlan | None = None,
        on_phase: Callable[..., Any] | None = None,
        last_visit: dict | None = None,
        person: dict | None = None,
        persisted_gaps: list[dict] | None = None,
        control_state: dict | None = None,
    ) -> TurnResult:
        used_plan = plan
        if used_plan is None:
            await _emit(on_phase, "planning", "Reading your story…")
            used_plan = await self.plan_turn(
                text,
                context={
                    "concern": concern,
                    "prior_facts": prior_facts,
                    "recent_turns": (recent_turns or [])[-12:],
                    "problem": problem,
                    "last_visit": last_visit or {},
                    "person": person or {},
                },
            )
        fact_rows = plan_to_fact_rows(used_plan) if used_plan else []
        guide_actions = guide_candidates_to_actions(used_plan) if used_plan else []
        wants_literature = bool(used_plan and (used_plan.wants_evidence or used_plan.literature_queries))
        result = orchestrate(
            text,
            prior_facts=prior_facts,
            asked=asked,
            answered=answered,
            current_closes=current_closes,
            concern=concern,
            audience=audience,
            turn_count=turn_count,
            llm_fact_rows=fact_rows or None,
            guide_actions=guide_actions or None,
            wants_evidence=wants_literature,
            persisted_gaps=persisted_gaps,
            control_state=control_state,
        )
        citations: list[dict] = []
        if wants_literature or result.action.type == "retrieve_evidence":
            from app.discovery.literature import retrieve_citations

            query = ""
            if used_plan and used_plan.literature_queries:
                query = str(used_plan.literature_queries[0])
            if len(query) < 4:
                query = (concern or text)[:180]
            if len(query) >= 4:
                await _emit(on_phase, "evidence", "Looking up related research…")
                citations = await retrieve_citations(query)
        result.citations = citations
        await _emit(on_phase, "speaking", "Writing a reply…")
        spoken = await self.compose_turn(
            action=result.action,
            safety_state=result.safety_status,
            problem=result.problem_representation,
            audience=audience,
            plan=used_plan,
            person=person,
            citations=citations,
            last_user_turn=text,
        )
        if result.safety_status != "S4":
            result.message = pick_verbalization(result.message, spoken)
        if used_plan and used_plan.problem_representation and critic_allows(used_plan.problem_representation):
            result.problem_representation = used_plan.problem_representation
        result.llm_used = bool(used_plan) or result.llm_used
        result.guide_plan = used_plan.model_dump() if used_plan else None
        if used_plan and used_plan.uncertainty_updates:
            extra = [item for item in used_plan.uncertainty_updates if item not in result.unknowns]
            result.unknowns = [*result.unknowns, *extra][:12]
        if turn_count == 0 and last_visit and last_visit.get("has_history"):
            from app.discovery.context import last_visit_opener

            opener = last_visit_opener(last_visit)
            if opener and opener.lower() not in result.message.lower():
                result.message = (opener + result.message).strip()
        return result


def merge_guide_facts(base, proposed: list[dict[str, Any]]):
    return merge_llm_facts(base, proposed, allow_open=True)
