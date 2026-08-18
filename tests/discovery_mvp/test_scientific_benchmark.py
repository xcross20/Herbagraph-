"""Independent scientific benchmark. Expected answers come from the spec fixture."""

from __future__ import annotations

import pytest

from app.discovery.scientific_benchmark import grade_case, load_cases, observed_from_product


def test_benchmark_fixture_rejects_current_style_diagnosis():
    cases = {item["id"]: item for item in load_cases()}
    emg = cases["SF-EMG-01"]
    bad = {
        "statement": "You have small-fiber neuropathy.",
        "provenance": [],
        "coverage": {"emg_ncs": {"small_fiber_density": "does_not_directly_assess"}},
    }
    score = grade_case(emg, bad)
    assert score.passed is False
    assert any("forbidden" in item or "provenance" in item for item in score.failures)


def test_grader_ignores_self_reported_must_entail():
    cases = {item["id"]: item for item in load_cases()}
    emg = cases["SF-EMG-01"]
    fake = {
        "statement": "something unrelated",
        "must_entail": list(emg["must_entail"]),
        "provenance": ["coverage-governor-v1"],
        "coverage": emg["coverage"],
    }
    score = grade_case(emg, fake)
    assert score.passed is False
    assert any(item.startswith("missing_entailment:") for item in score.failures)


async def _case_and_map(client, presenting_concern: str, *, emg: bool = False) -> tuple[dict, dict]:
    created = await client.post("/api/v1/cases", json={"presenting_concern": presenting_concern})
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    if emg:
        attached = await client.post(
            f"/api/v1/cases/{case_id}/documents",
            json={
                "filename": "emg-report.txt",
                "text": "Needle EMG and nerve conduction studies were normal.",
            },
        )
        assert attached.status_code == 200, attached.text
    fetched = await client.get(f"/api/v1/cases/{case_id}")
    assert fetched.status_code == 200, fetched.text
    mapped = await client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert mapped.status_code == 200, mapped.text
    return fetched.json(), mapped.json()


@pytest.mark.asyncio
async def test_benchmark_grades_small_fiber_emg_api_output(authed_client):
    cases = {item["id"]: item for item in load_cases()}
    case_payload, map_payload = await _case_and_map(
        authed_client,
        "For six months my feet have burned at night.",
        emg=True,
    )
    score = grade_case(cases["SF-EMG-01"], observed_from_product(case_payload, map_payload))
    assert score.passed is True, score.failures


@pytest.mark.asyncio
async def test_benchmark_grades_biliary_emg_api_output(authed_client):
    cases = {item["id"]: item for item in load_cases()}
    case_payload, map_payload = await _case_and_map(
        authed_client,
        "I think this is my gallbladder. I also had an EMG.",
        emg=True,
    )
    score = grade_case(cases["BIL-EMG-01"], observed_from_product(case_payload, map_payload))
    assert score.passed is True, score.failures


@pytest.mark.asyncio
async def test_benchmark_grades_correction_history_from_api(authed_client, db_session):
    import uuid

    from sqlalchemy import select

    from app.discovery.engine import CaseSnapshot, FindingDraft
    from app.discovery.service import apply_snapshot, persist_map_version, snapshot_from_case
    from app.models.discovery import DiscoveryCase

    cases = {item["id"]: item for item in load_cases()}
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "Onset was after surgery. Correction: before surgery. Correction: after surgery."},
    )
    assert created.status_code == 201, created.text
    case_id = uuid.UUID(created.json()["id"])
    case = (await db_session.execute(select(DiscoveryCase).where(DiscoveryCase.id == case_id))).scalar_one()

    def snap(value: str) -> CaseSnapshot:
        return CaseSnapshot(
            presenting_concern=case.presenting_concern,
            findings=[
                FindingDraft(kind="context", name="onset", value=value, status=None, branch=None, source="user")
            ],
            hypotheses=[],
            branch_coverage=[],
            investigation_coverage=0.0,
        )

    await apply_snapshot(db_session, case, snap("after surgery"), source_event_id="bench-a")
    await apply_snapshot(db_session, case, snap("before surgery"), source_event_id="bench-b")
    await apply_snapshot(db_session, case, snap("after surgery"), source_event_id="bench-a2")
    await persist_map_version(db_session, case, snapshot_from_case(case))
    await db_session.commit()
    fetched = await authed_client.get(f"/api/v1/cases/{case_id}")
    mapped = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert fetched.status_code == 200
    assert mapped.status_code == 200
    score = grade_case(cases["CORR-ABA-01"], observed_from_product(fetched.json(), mapped.json()))
    assert score.passed is True, score.failures


@pytest.mark.asyncio
async def test_benchmark_grades_safety_escalation_api_output(authed_client):
    cases = {item["id"]: item for item in load_cases()}
    created = await authed_client.post(
        "/api/v1/cases",
        json={"presenting_concern": "Chest pain and I cannot catch my breath."},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    follow = await authed_client.post(
        f"/api/v1/cases/{case_id}/turns",
        json={"text": "It is still happening on this return visit."},
    )
    assert follow.status_code == 200, follow.text
    mapped = await authed_client.get(f"/api/v1/cases/{case_id}/investigation-map")
    assert mapped.status_code == 200, mapped.text
    score = grade_case(cases["SAFE-S3-01"], observed_from_product(follow.json(), mapped.json()))
    assert score.passed is True, score.failures
