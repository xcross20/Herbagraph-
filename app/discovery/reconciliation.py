"""Turn a validated Guide plan plus user text into a MutationBatch."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.branch_service import branches_from_concern, default_gaps_for, evidence_for_workup
from app.discovery.epistemics import EpistemicValidator, gallbladder_split
from app.discovery.mutations import (
    CorrectionMutation,
    FindingMutation,
    GapMutation,
    MutationBatch,
    TimelineMutation,
    WorkupMutation,
    apply_mutation_batch,
)
from app.discovery.workup_service import result_state_from_recollection, workup_from_text
from app.models.discovery import DiscoveryCase


def batch_from_turn(*, text: str, concern: str | None, plan: dict[str, Any] | None) -> MutationBatch:
    validator = EpistemicValidator()
    batch = MutationBatch()
    plan = plan or {}
    split = gallbladder_split(text)
    if split:
        finding = split["finding"]
        batch.add_findings.append(
            FindingMutation(name=finding["concept"], value=finding["value"], kind=finding["kind"], raw_text=text)
        )
        batch.add_interpretations.append(split["interpretation"])
    for item in plan.get("reported_facts") or plan.get("reported_findings") or []:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept") or item.get("name") or "").strip()
        if not concept:
            continue
        decision = validator.validate_finding(concept, concept=concept, kind=str(item.get("type") or "symptom"))
        if not decision.allowed:
            if any(mod.get("action") == "store_as_interpretation" for mod in decision.modifications):
                batch.add_interpretations.append({"statement": concept, "concept": concept})
            continue
        batch.add_findings.append(
            FindingMutation(
                name=concept[:180],
                value=str(item.get("value") or "reported"),
                kind=str(item.get("type") or item.get("kind") or "symptom"),
                raw_text=str(item.get("raw_text") or ""),
            )
        )
    for item in plan.get("patient_interpretations") or []:
        if isinstance(item, dict):
            statement = str(item.get("statement") or item.get("concept") or "").strip()
            concept = item.get("concept")
        else:
            statement = str(item).strip()
            concept = None
        if statement and validator.validate_interpretation(statement).allowed:
            batch.add_interpretations.append({"statement": statement, "concept": concept})
    for item in plan.get("timeline_events") or []:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            date_text = item.get("date_text")
        else:
            label = str(item).strip()
            date_text = None
        if label:
            batch.add_timeline_events.append(TimelineMutation(label=label, date_text=date_text))
    for item in plan.get("timeline_updates") or []:
        label = str(item).strip() if not isinstance(item, dict) else str(item.get("label") or item.get("event") or "")
        if label and not any(event.label == label for event in batch.add_timeline_events):
            batch.add_timeline_events.append(TimelineMutation(label=label))
    for item in plan.get("prior_workup_updates") or plan.get("prior_workup") or []:
        if isinstance(item, dict):
            test = str(item.get("test") or item.get("raw_test_name") or "").strip()
            result = str(item.get("result") or item.get("result_summary") or "")
        else:
            test = str(item).strip()
            result = ""
        if test:
            batch.add_prior_workup.append(
                WorkupMutation(
                    raw_test_name=test,
                    result_summary=result or None,
                    result_state=result_state_from_recollection(result),
                )
            )
    if not batch.add_prior_workup:
        batch.add_prior_workup.extend(workup_from_text(text))
    extra = " ".join(
        filter(
            None,
            [text, concern, *[item.name for item in batch.add_findings]],
        )
    )
    batch.open_branches = branches_from_concern(concern or text, extra)
    for branch in batch.open_branches:
        batch.open_gaps.extend(default_gaps_for(branch.code))
    for work in batch.add_prior_workup:
        for branch in batch.open_branches:
            link = evidence_for_workup(work.raw_test_name, branch.code)
            if link is not None:
                batch.add_branch_evidence.append(link)
    for item in plan.get("corrections") or []:
        if isinstance(item, dict) and item.get("reason"):
            batch.add_corrections.append(
                CorrectionMutation(
                    reason=str(item.get("reason")),
                    original_text=item.get("from") or item.get("original_text"),
                    replacement_text=item.get("to") or item.get("replacement_text"),
                )
            )
    for item in plan.get("evidence_gap_updates") or []:
        if isinstance(item, dict) and item.get("label"):
            batch.open_gaps.append(
                GapMutation(
                    code=str(item.get("code") or item.get("label") or "gap")[:80],
                    label=str(item.get("label")),
                    branch_code=item.get("branch_code"),
                    description=item.get("description"),
                )
            )
    return batch


async def persist_turn_v2(
    db: AsyncSession,
    case: DiscoveryCase,
    *,
    text: str,
    plan: dict[str, Any] | None,
) -> None:
    batch = batch_from_turn(text=text, concern=case.presenting_concern, plan=plan)
    await apply_mutation_batch(db, case, batch)
