"""Discovery Guide Phase A: LLM-led plan, deterministic validation."""

import pytest

from app.discovery.guide import (
    DiscoveryGuide,
    DiscoveryTurnPlan,
    NextActionCandidate,
    guide_candidates_to_actions,
    plan_to_fact_rows,
    validate_plan,
)
from app.discovery.orchestrator import orchestrate
from app.discovery.safety import screen_safety


FACIAL = (
    "I've been having this pressure on the right side of my face for almost a year. "
    "It started a few weeks after I got shocked. Sometimes my ear feels full, "
    "sometimes my face feels swollen, but I'm not even sure it's actually swollen. "
    "MRI was normal and someone told me trigeminal neuralgia wasn't likely."
)

@pytest.fixture(autouse=True)
def _no_live_guide_llm(monkeypatch):
    monkeypatch.setattr("app.discovery.guide.discovery_llm_ready", lambda: False)


GALLBLADDER = (
    "I've been dealing with this weird pain under my right ribs for eight months. "
    "I think it's my gallbladder because fatty food makes it worse, but my ultrasound was apparently normal."
)


def _facial_plan() -> DiscoveryTurnPlan:
    return validate_plan(
        {
            "reported_facts": [
                {"concept": "right-sided facial pressure", "type": "symptom"},
                {"concept": "ear fullness", "type": "symptom"},
                {"concept": "subjective facial swelling", "type": "symptom"},
                {"concept": "trigeminal neuralgia", "type": "symptom"},
            ],
            "patient_interpretations": ["possible connection to electrical injury"],
            "timeline_updates": ["electrical injury", "symptoms began several weeks later"],
            "prior_workup": [{"test": "brain MRI", "result": "reported normal"}],
            "uncertainty_updates": ["whether swelling is objectively visible"],
            "action_candidates": [
                {
                    "type": "ASK_QUESTION",
                    "prompt": "When your face feels swollen, has anyone else been able to see it, or is it only something you feel?",
                    "reason": "Subjective vs objective swelling changes the investigation.",
                    "options": ["Only I notice it", "Others have seen it", "Not sure"],
                }
            ],
            "recommended_next_action": {
                "type": "ASK_QUESTION",
                "prompt": "When your face feels swollen, has anyone else been able to see it, or is it only something you feel?",
            },
            "problem_representation": (
                "Chronic unilateral right facial pressure with subjective swelling and intermittent ear fullness, "
                "beginning weeks after electrical injury, with brain MRI reportedly normal."
            ),
        }
    )


def test_validate_plan_drops_diagnosis_findings():
    plan = _facial_plan()
    names = [item.concept.lower() for item in plan.reported_facts]
    assert "right-sided facial pressure" in names
    assert "ear fullness" in names
    assert not any("trigeminal" in name for name in names)
    assert all(row["verification"] == "patient_reported" for row in plan.prior_workup)


def test_validate_plan_coerces_object_interpretations():
    plan = validate_plan(
        {
            "reported_facts": [
                {"concept": "right upper abdominal pain", "type": "symptom"},
                "worse lifting very heavy things",
            ],
            "patient_interpretations": [
                {
                    "concept": "gallbladder",
                    "value": "worse after fatty food and lifting very heavy things",
                }
            ],
            "timeline_updates": [{"event": "started eight months ago", "note": "after moving house"}],
            "prior_workup": ["ultrasound reportedly normal"],
            "uncertainty_updates": {"question": "whether the ultrasound was complete"},
        }
    )
    interps = " ".join(plan.patient_interpretations).lower()
    assert "gallbladder" in interps
    assert "lifting very heavy things" in interps
    assert any("eight months" in item.lower() for item in plan.timeline_updates)
    assert plan.prior_workup[0]["test"]
    assert plan.uncertainty_updates
    names = [item.concept.lower() for item in plan.reported_facts]
    assert "right upper abdominal pain" in names
    assert any("lifting" in name for name in names)


def test_validate_plan_keeps_many_threads_from_a_messy_story():
    facts = [{"concept": f"thread {index} unusual symptom", "type": "symptom"} for index in range(24)]
    interps = [f"theory {index} about the odd pattern" for index in range(12)]
    plan = validate_plan(
        {
            "reported_facts": [*facts, {"concept": "trigeminal neuralgia"}],
            "patient_interpretations": interps,
            "timeline_updates": [f"year {index} flare after an odd trigger" for index in range(12)],
            "problem_representation": (
                "A long messy multi-year story with many threads, not a diagnosis."
            ),
        }
    )
    assert len(plan.reported_facts) >= 20
    assert len(plan.patient_interpretations) >= 12
    assert len(plan.timeline_updates) >= 12
    assert not any("trigeminal" in item.concept for item in plan.reported_facts)


def test_validate_plan_does_not_raise_on_hostile_shapes():
    plan = validate_plan(
        {
            "patient_interpretations": [None, 12, {"nested": {"x": 1}}],
            "reported_facts": "just pain under the ribs",
            "recommended_next_action": "What happens when you lift something heavy?",
            "action_candidates": [
                {
                    "type": "ASK_QUESTION",
                    "prompt": "What happens when you lift something heavy?",
                    "options": [{"label": "worse"}, "same"],
                }
            ],
        }
    )
    assert isinstance(plan, DiscoveryTurnPlan)
    assert plan.reported_facts
    assert plan.recommended_next_action is not None
    assert plan.action_candidates[0].options == ["worse", "same"]


@pytest.mark.asyncio
async def test_guide_opening_uses_case_specific_question():
    result = await DiscoveryGuide().process_turn(
        FACIAL,
        prior_facts={},
        asked=[],
        answered=set(),
        concern=FACIAL,
        turn_count=0,
        plan=_facial_plan(),
    )
    assert result.llm_used is True
    names = {item.name for item in result.new_findings}
    assert "right-sided facial pressure" in names
    assert "ear fullness" in names
    assert "prior_workup" in names
    assert "patient_interpretation" in names
    assert not any("trigeminal" in item.name for item in result.new_findings)
    assert result.action.type == "ask_question"
    assert "swollen" in (result.action.prompt or "").lower()
    assert "you have" not in result.message.lower()
    assert "trigeminal neuralgia" not in result.message.lower()
    assert "electrical injury" in result.problem_representation.lower()


@pytest.mark.asyncio
async def test_guide_cannot_override_s4():
    plan = validate_plan(
        {
            "action_candidates": [
                {"type": "ASK_QUESTION", "prompt": "On a scale of 1-10, how bad is the pain?"}
            ],
            "recommended_next_action": {
                "type": "ASK_QUESTION",
                "prompt": "On a scale of 1-10, how bad is the pain?",
            },
        }
    )
    text = "It started this morning and now I can't lift my right foot."
    assert screen_safety(text).status == "S4"
    result = await DiscoveryGuide().process_turn(
        text,
        prior_facts={},
        asked=[],
        answered=set(),
        plan=plan,
    )
    assert result.safety_status == "S4"
    assert result.action.type == "show_safety_message"
    assert "1-10" not in result.message.lower()


@pytest.mark.asyncio
async def test_no_plan_falls_back_to_deterministic_laterality():
    result = await DiscoveryGuide().process_turn(
        "For six months, my feet have burned at night. My doctor says my blood work is normal.",
        prior_facts={},
        asked=[],
        answered=set(),
        turn_count=0,
        plan=None,
    )
    assert result.action.question_id == "q_laterality"
    assert result.llm_used is False


@pytest.mark.asyncio
async def test_gallbladder_story_keeps_theory_as_interpretation():
    plan = validate_plan(
        {
            "reported_facts": [
                {"concept": "right upper abdominal pain", "type": "symptom"},
                {"concept": "worse after fatty food", "type": "context"},
            ],
            "patient_interpretations": ["I think it's my gallbladder"],
            "prior_workup": [{"test": "ultrasound", "result": "reportedly normal"}],
            "action_candidates": [
                {
                    "type": "ASK_QUESTION",
                    "prompt": "When this happens, is it mild and brief or severe and lasting hours?",
                    "options": ["Mild and brief", "Severe and lasting", "Not sure"],
                }
            ],
        }
    )
    result = await DiscoveryGuide().process_turn(
        GALLBLADDER,
        prior_facts={},
        asked=[],
        answered=set(),
        plan=plan,
    )
    names = {item.name: item.value for item in result.new_findings}
    assert "patient_interpretation" in names
    assert "cholecystitis" not in names
    assert result.action.type != "show_safety_message"
    assert "cholecystitis" not in result.message.lower()
    assert "you have" not in result.message.lower()


def test_guide_candidates_are_scored_below_safety():
    plan = DiscoveryTurnPlan(
        action_candidates=[
            NextActionCandidate(type="ASK_QUESTION", prompt="What color are your eyes?", reason="demo")
        ]
    )
    actions = guide_candidates_to_actions(plan)
    assert actions[0].score < 0.96
    assert actions[0].type == "ask_question"


def test_plan_to_fact_rows_marks_workup_unverified():
    rows = plan_to_fact_rows(_facial_plan())
    work = next(item for item in rows if item["name"] == "prior_workup")
    assert "patient_reported" in work["value"]
    assert work["kind"] == "assessment"


def test_orchestrate_still_ignores_denied_open_facts():
    result = orchestrate(
        "My face hurts.",
        prior_facts={},
        asked=[],
        answered=set(),
        llm_fact_rows=[{"name": "trigeminal neuralgia", "value": "diagnosed"}],
    )
    assert all("trigeminal" not in item.name for item in result.new_findings)


def test_citation_lines_are_digit_only_pmids():
    from app.discovery.guide import citation_lines

    lines = citation_lines(
        [
            {"title": "B12 and metformin", "pmid": "12345678"},
            {"title": "Invented", "pmid": "pending"},
            {"title": "Also invented", "pmid": "PMID 99"},
            {"title": "", "pmid": "11122233"},
        ]
    )
    assert lines == ["B12 and metformin (PMID 12345678)"]


@pytest.mark.asyncio
async def test_compose_turn_passes_person_and_real_citations_only(monkeypatch):
    captured: dict = {}

    async def fake_json(_system, user):
        captured["user"] = user
        return {"message": "Maya, the night burning still sits next to the low B12 on file. Has it changed?"}

    monkeypatch.setattr("app.discovery.guide.discovery_llm_ready", lambda: True)
    monkeypatch.setattr("app.discovery.guide.try_llm_json", fake_json)
    from app.discovery.actions import NextAction

    spoken = await DiscoveryGuide().compose_turn(
        action=NextAction(
            type="ask_question",
            prompt="Has the burning changed?",
            objective="Clarify change",
            score=0.8,
        ),
        safety_state="S0",
        problem="night burning with low B12",
        audience="consumer",
        plan=None,
        person={"first_name": "Maya", "labs": [{"name": "Vitamin B12", "status": "low"}]},
        citations=[
            {"title": "B12 and metformin", "pmid": "12345678"},
            {"title": "fake", "pmid": "not-a-pmid"},
        ],
    )
    assert spoken and "Maya" in spoken
    assert "first_name" in captured["user"]
    assert "12345678" in captured["user"]
    assert "not-a-pmid" not in captured["user"]


@pytest.mark.asyncio
async def test_plan_turn_includes_person_context(monkeypatch):
    captured: dict = {}

    async def fake_json(_system, user, **_kwargs):
        captured["user"] = user
        return {
            "reported_facts": [{"concept": "burning feet", "type": "symptom"}],
            "action_candidates": [{"type": "ASK_QUESTION", "prompt": "Is it both feet?"}],
        }

    monkeypatch.setattr("app.discovery.guide.discovery_llm_ready", lambda: True)
    monkeypatch.setattr("app.discovery.guide.try_llm_json", fake_json)
    await DiscoveryGuide().plan_turn(
        "My feet still burn at night.",
        context={
            "concern": "burning feet",
            "prior_facts": {"medications": "metformin"},
            "person": {"first_name": "Maya", "meds": ["metformin"]},
            "last_visit": {"summary": "burning feet"},
        },
    )
    assert "person_context" in captured["user"]
    assert "Maya" in captured["user"]
    assert "metformin" in captured["user"]
