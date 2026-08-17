"""Hostile persist invariants. These must fail until V2 memory is trustworthy."""

import uuid

import pytest
from sqlalchemy import select

from app.discovery.epistemics import EpistemicValidator
from app.discovery.reconciliation import batch_from_turn, persist_turn_v2
from app.discovery.service import rebuild_case
from app.models.discovery import (
    DiscoveryBranchEvidence,
    DiscoveryCase,
    DiscoveryEvidenceGap,
    DiscoveryFinding,
    DiscoveryInvestigationBranch,
    DiscoveryPriorWorkupItem,
    DiscoveryReasoningClaim,
    DiscoveryReasoningCorrection,
)
from app.models.enums import (
    DiscoveryBranchStatus,
    DiscoveryCaseStatus,
    DiscoveryClaimStatus,
    DiscoveryEvidenceRelationship,
)
from app.models.user import User


async def _case(db_session, concern: str) -> DiscoveryCase:
    user = User(email=f"inv-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    case = DiscoveryCase(
        user_id=user.id,
        presenting_concern=concern,
        status=DiscoveryCaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    return case


@pytest.mark.asyncio
async def test_gallbladder_then_emg_does_not_attach_to_biliary(db_session):
    case = await _case(db_session, "My gallbladder hurts.")
    await persist_turn_v2(db_session, case, text="My gallbladder hurts.", plan=None)
    await persist_turn_v2(db_session, case, text="EMG was normal.", plan=None)
    biliary = (
        await db_session.execute(
            select(DiscoveryInvestigationBranch).where(
                DiscoveryInvestigationBranch.case_id == case.id,
                DiscoveryInvestigationBranch.code == "biliary_colic_pattern",
            )
        )
    ).scalar_one()
    links = list(
        (
            await db_session.execute(
                select(DiscoveryBranchEvidence).where(DiscoveryBranchEvidence.branch_id == biliary.id)
            )
        ).scalars()
    )
    assert not any(item.relationship == DiscoveryEvidenceRelationship.INCONCLUSIVE for item in links)
    assert not any("emg" in (item.rationale or "").lower() for item in links)


@pytest.mark.asyncio
async def test_burning_feet_normal_emg_persists_does_not_address(db_session):
    case = await _case(db_session, "For six months my feet have burned at night.")
    await persist_turn_v2(db_session, case, text="For six months my feet have burned at night.", plan=None)
    await persist_turn_v2(db_session, case, text="EMG was normal.", plan=None)
    fiber = (
        await db_session.execute(
            select(DiscoveryInvestigationBranch).where(
                DiscoveryInvestigationBranch.case_id == case.id,
                DiscoveryInvestigationBranch.code == "small_fiber_function",
            )
        )
    ).scalar_one()
    links = list(
        (
            await db_session.execute(
                select(DiscoveryBranchEvidence).where(DiscoveryBranchEvidence.branch_id == fiber.id)
            )
        ).scalars()
    )
    assert any(item.relationship == DiscoveryEvidenceRelationship.DOES_NOT_ADDRESS for item in links)
    assert fiber.status != DiscoveryBranchStatus.CONDITIONALLY_RESOLVED
    assert fiber.resolved_at is None


@pytest.mark.asyncio
async def test_replayed_turn_does_not_duplicate_rows(db_session):
    case = await _case(db_session, "My gallbladder hurts.")
    text = "My gallbladder hurts."
    await persist_turn_v2(db_session, case, text=text, plan=None)
    await persist_turn_v2(db_session, case, text=text, plan=None)
    findings = list(
        (await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))).scalars()
    )
    gaps = list(
        (await db_session.execute(select(DiscoveryEvidenceGap).where(DiscoveryEvidenceGap.case_id == case.id))).scalars()
    )
    branches = list(
        (
            await db_session.execute(
                select(DiscoveryInvestigationBranch).where(DiscoveryInvestigationBranch.case_id == case.id)
            )
        ).scalars()
    )
    workup = list(
        (
            await db_session.execute(
                select(DiscoveryPriorWorkupItem).where(DiscoveryPriorWorkupItem.case_id == case.id)
            )
        ).scalars()
    )
    names = [(item.name, item.value) for item in findings if item.is_active]
    assert len(names) == len(set(names))
    gap_codes = [item.code for item in gaps]
    assert len(gap_codes) == len(set(gap_codes))
    branch_codes = [item.code for item in branches]
    assert len(branch_codes) == len(set(branch_codes))
    workup_keys = [(item.raw_test_name, item.result_state) for item in workup]
    assert len(workup_keys) == len(set(workup_keys))


@pytest.mark.asyncio
async def test_thanks_does_not_duplicate_findings_or_gaps(db_session):
    case = await _case(db_session, "My gallbladder hurts.")
    await persist_turn_v2(db_session, case, text="My gallbladder hurts.", plan=None)
    findings_before = (
        await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    gaps_before = (
        await db_session.execute(select(DiscoveryEvidenceGap).where(DiscoveryEvidenceGap.case_id == case.id))
    ).scalars().all()
    await persist_turn_v2(db_session, case, text="thanks", plan=None)
    findings_after = (
        await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))
    ).scalars().all()
    gaps_after = (
        await db_session.execute(select(DiscoveryEvidenceGap).where(DiscoveryEvidenceGap.case_id == case.id))
    ).scalars().all()
    assert len(findings_after) == len(findings_before)
    assert len(gaps_after) == len(gaps_before)


@pytest.mark.asyncio
async def test_correction_keeps_old_row_inactive_and_rebuild_does_not_restore(db_session):
    case = await _case(db_session, "Abdominal pain following an operation")
    await persist_turn_v2(
        db_session,
        case,
        text="Pain started after surgery.",
        plan={"reported_facts": [{"concept": "onset", "type": "context", "value": "after surgery"}]},
    )
    await persist_turn_v2(
        db_session,
        case,
        text="Actually it started two months before surgery.",
        plan={
            "corrections": [
                {
                    "reason": "user correction",
                    "from": "after surgery",
                    "to": "two months before surgery",
                    "original_text": "after surgery",
                    "replacement_text": "two months before surgery",
                }
            ]
        },
    )
    rows = list(
        (await db_session.execute(select(DiscoveryFinding).where(DiscoveryFinding.case_id == case.id))).scalars()
    )
    old = [item for item in rows if item.value == "after surgery"]
    new = [item for item in rows if item.value == "two months before surgery" and item.is_active]
    assert old
    assert all(item.is_active is False for item in old)
    assert new
    assert new[0].supersedes_finding_id == old[0].id
    claims = list(
        (
            await db_session.execute(
                select(DiscoveryReasoningClaim).where(DiscoveryReasoningClaim.case_id == case.id)
            )
        ).scalars()
    )
    corrections = list(
        (
            await db_session.execute(
                select(DiscoveryReasoningCorrection).where(DiscoveryReasoningCorrection.case_id == case.id)
            )
        ).scalars()
    )
    assert corrections
    original = next(item for item in claims if item.status == DiscoveryClaimStatus.SUPERSEDED)
    replacement = next(item for item in claims if item.id == corrections[0].replacement_claim_id)
    assert corrections[0].original_claim_id == original.id
    assert replacement.status == DiscoveryClaimStatus.ACTIVE
    await rebuild_case(db_session, case)
    extras = (
        await db_session.execute(
            select(DiscoveryFinding).where(
                DiscoveryFinding.case_id == case.id,
                DiscoveryFinding.is_active.is_(True),
            )
        )
    ).scalars().all()
    assert all(item.value != "after surgery" for item in extras)
    snapshot = case.snapshot or ""
    assert "after surgery" not in snapshot


@pytest.mark.asyncio
async def test_non_addressing_test_cannot_close_branch(db_session):
    case = await _case(db_session, "For six months my feet have burned at night.")
    await persist_turn_v2(db_session, case, text="For six months my feet have burned at night.", plan=None)
    decision = EpistemicValidator().validate_branch_resolution(
        relation="does_not_directly_assess",
        proposed_close=True,
    )
    assert decision.allowed is False
    await persist_turn_v2(
        db_session,
        case,
        text="EMG was normal so we can close the small-fiber question.",
        plan={
            "branch_updates": [
                {
                    "branch_code": "small_fiber_function",
                    "proposed_label": "Small-fiber function",
                    "operation": "CLOSE",
                    "rationale": "EMG normal",
                }
            ],
            "prior_workup": [{"test": "EMG", "result": "normal"}],
        },
    )
    fiber = (
        await db_session.execute(
            select(DiscoveryInvestigationBranch).where(
                DiscoveryInvestigationBranch.case_id == case.id,
                DiscoveryInvestigationBranch.code == "small_fiber_function",
            )
        )
    ).scalar_one()
    assert fiber.status != DiscoveryBranchStatus.CONDITIONALLY_RESOLVED
    assert fiber.resolved_at is None


def test_batch_from_turn_emits_supersede_for_active_finding_correction():
    batch = batch_from_turn(
        text="Actually it started before surgery.",
        concern="Pain after surgery",
        plan={
            "corrections": [
                {
                    "reason": "user correction",
                    "from": "after surgery",
                    "to": "before surgery",
                    "original_text": "after surgery",
                    "replacement_text": "before surgery",
                }
            ]
        },
    )
    assert batch.supersede_findings
    assert batch.supersede_findings[0].previous_value == "after surgery"
    assert batch.supersede_findings[0].value == "before surgery"


@pytest.mark.asyncio
async def test_branch_and_gap_unique_constraints_block_duplicates(db_session):
    from sqlalchemy.exc import IntegrityError

    case = await _case(db_session, "My gallbladder hurts.")
    await persist_turn_v2(db_session, case, text="My gallbladder hurts.", plan=None)
    from app.models.discovery import DiscoveryInvestigationBranch

    db_session.add(
        DiscoveryInvestigationBranch(
            case_id=case.id,
            code="biliary_colic_pattern",
            label="dup",
            category="biliary",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
