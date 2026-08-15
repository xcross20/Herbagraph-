"""Discovery Guide — LLM-led consultation with deterministic validation."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

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


class DiscoveryTurnPlan(BaseModel):
    user_intents: list[str] = Field(default_factory=list)
    reported_facts: list[CandidateFinding] = Field(default_factory=list)
    patient_interpretations: list[str] = Field(default_factory=list)
    timeline_updates: list[str] = Field(default_factory=list)
    prior_workup: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    uncertainty_updates: list[str] = Field(default_factory=list)
    literature_queries: list[str] = Field(default_factory=list)
    action_candidates: list[NextActionCandidate] = Field(default_factory=list)
    recommended_next_action: NextActionCandidate | None = None
    problem_representation: str = ""
    missing_dimensions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    wants_evidence: bool = False


def validate_plan(raw: dict[str, Any] | None) -> DiscoveryTurnPlan:
    plan = DiscoveryTurnPlan.model_validate(raw or {})
    kept: list[CandidateFinding] = []
    for item in plan.reported_facts:
        concept = (item.concept or "").strip()
        if not concept or is_denied_concept(concept):
            continue
        kind = item.type if item.type in {"symptom", "context", "assessment"} else "symptom"
        kept.append(
            CandidateFinding(
                concept=concept[:160],
                type=kind,
                value=(item.value or "reported")[:200],
                verification="patient_reported",
            )
        )
    plan.reported_facts = kept[:16]
    plan.patient_interpretations = [
        item.strip()[:200] for item in plan.patient_interpretations if item and not is_denied_concept(item)
    ][:8]
    plan.timeline_updates = [item.strip()[:200] for item in plan.timeline_updates if item][:8]
    workup: list[dict[str, Any]] = []
    for row in plan.prior_workup:
        test = str(row.get("test") or "").strip()
        if not test:
            continue
        workup.append(
            {
                "test": test[:120],
                "result": str(row.get("result") or "mentioned")[:160],
                "verification": "patient_reported",
            }
        )
    plan.prior_workup = workup[:8]
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
    plan.uncertainty_updates = [item.strip()[:160] for item in plan.uncertainty_updates if item][:8]
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
                "Produce the DiscoveryTurnPlan JSON. Integrate person_context. "
                "Do not diagnose. Do not invent labs or citations."
            ),
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
                f"problem={problem}\n"
                f"unknowns={list((plan.missing_dimensions if plan else [])[:6])}\n"
                f"person_context={person or {}}\n"
                f"retrieved_citations={cite_lines}\n"
                "Write the user-facing message for this person. Reflect, integrate what we already know about them, "
                "then include the required question if provided. Mention a citation only if retrieved_citations is non-empty."
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
