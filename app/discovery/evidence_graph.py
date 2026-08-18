"""Persist workup items and typed evidence edges. Unknown coverage writes no edge."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.coverage_catalog import concepts_for_branch, test_code_for_finding
from app.discovery.evidence_interpreter import interpret_workup
from app.discovery.identity import evidence_identity_key
from app.discovery.resolver import resolve_test
from app.models.discovery import (
    DiscoveryEvidenceEdge,
    DiscoveryFinding,
    DiscoveryHypothesis,
    DiscoveryWorkupItem,
)
from app.models.enums import EvidenceRelationship, ResolverStatus


def workup_identity_key(*, case_id: uuid.UUID, test_code: str, source_event_id: str) -> str:
    material = "|".join((str(case_id), test_code, source_event_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _result_state_from_value(value: str | None) -> str | None:
    blob = (value or "").lower()
    if "reported_normal" in blob or blob in {"normal", "negative"}:
        return "negative"
    if "reported_abnormal" in blob or blob in {"abnormal", "positive"}:
        return "positive"
    if blob in {"mentioned", "attached", "uploaded"}:
        return None
    return None


async def persist_evidence_graph(
    db: AsyncSession,
    *,
    case_id: uuid.UUID,
    source_event_id: str,
) -> list[DiscoveryEvidenceEdge]:
    findings = list(
        (
            await db.execute(
                select(DiscoveryFinding).where(
                    DiscoveryFinding.case_id == case_id,
                    DiscoveryFinding.active.is_(True),
                )
            )
        ).scalars()
    )
    hypotheses = list(
        (await db.execute(select(DiscoveryHypothesis).where(DiscoveryHypothesis.case_id == case_id))).scalars()
    )
    branch_codes: list[str] = []
    for hypo in hypotheses:
        branch_codes.extend(concepts_for_branch(hypo.code))
        branch_codes.extend(concepts_for_branch(hypo.branch or ""))
        if hypo.code:
            branch_codes.append(hypo.code)
        if hypo.branch:
            branch_codes.append(hypo.branch)
    branch_codes = list(dict.fromkeys(branch_codes))

    written: list[DiscoveryEvidenceEdge] = []
    seen_tests: set[str] = set()
    for finding in findings:
        test_code = test_code_for_finding(finding.name)
        resolved = resolve_test(finding.name)
        if test_code is None and resolved.status is ResolverStatus.MATCHED and resolved.match is not None:
            test_code = resolved.match.code
        if not test_code or test_code in seen_tests:
            continue
        seen_tests.add(test_code)
        raw_label = finding.name
        interpreted = interpret_workup(
            raw_label=raw_label,
            branch_codes=branch_codes,
            result_state=_result_state_from_value(finding.value),
        )
        workup_key = workup_identity_key(
            case_id=case_id, test_code=test_code, source_event_id=source_event_id
        )
        existing_workup = (
            await db.execute(
                select(DiscoveryWorkupItem).where(
                    DiscoveryWorkupItem.case_id == case_id,
                    DiscoveryWorkupItem.identity_key == workup_key,
                )
            )
        ).scalar_one_or_none()
        if existing_workup is None:
            existing_workup = DiscoveryWorkupItem(
                case_id=case_id,
                test_code=test_code,
                raw_label=raw_label,
                normalized_result=_result_state_from_value(finding.value),
                source_event_id=source_event_id,
                identity_key=workup_key,
            )
            db.add(existing_workup)
            await db.flush()

        for draft in interpreted.edges:
            identity = evidence_identity_key(
                case_id=case_id,
                branch_code=draft.branch_code,
                workup_key=workup_key,
                relationship=draft.relationship.value,
                version=1,
            )
            existing = (
                await db.execute(
                    select(DiscoveryEvidenceEdge).where(
                        DiscoveryEvidenceEdge.case_id == case_id,
                        DiscoveryEvidenceEdge.identity_key == identity,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                written.append(existing)
                continue
            prior = list(
                (
                    await db.execute(
                        select(DiscoveryEvidenceEdge).where(
                            DiscoveryEvidenceEdge.case_id == case_id,
                            DiscoveryEvidenceEdge.branch_code == draft.branch_code,
                            DiscoveryEvidenceEdge.workup_id == existing_workup.id,
                        )
                    )
                ).scalars()
            )
            if prior and any(item.relationship != draft.relationship for item in prior):
                explanation = f"contradiction:{draft.relationship.value}"
            else:
                explanation = draft.explanation
            row = DiscoveryEvidenceEdge(
                case_id=case_id,
                branch_code=draft.branch_code,
                workup_id=existing_workup.id,
                relationship=draft.relationship,
                version=1,
                explanation=explanation,
                identity_key=identity,
                coverage_relation=draft.coverage,
                rule_version=draft.rule_version,
                rationale=draft.rationale,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(row)
            written.append(row)
    await db.flush()
    return written


def contradictions_for(edges: list[DiscoveryEvidenceEdge]) -> list[str]:
    by_branch: dict[str, set[str]] = {}
    for edge in edges:
        by_branch.setdefault(edge.branch_code, set()).add(edge.relationship.value)
    found = []
    for branch, relations in by_branch.items():
        if EvidenceRelationship.SUPPORTS.value in relations and EvidenceRelationship.WEAKENS.value in relations:
            found.append(branch)
    return found
