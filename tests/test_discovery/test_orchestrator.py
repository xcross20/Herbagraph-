"""Turn orchestrator: Case mutates first, then an action, then speech. Never a diagnosis."""

from app.discovery.engine import FindingDraft
from app.discovery.intake import extract_facts, problem_representation
from app.discovery.orchestrator import orchestrate
from app.discovery.safety import screen_safety


FIXTURE = (
    "For six months, my feet have burned at night. My doctor says my blood work is normal."
)


def test_fixture_extracts_symptoms_not_a_diagnosis():
    facts = extract_facts(FIXTURE)
    names = {item.name for item in facts}
    assert "burning sensation" in names
    assert "location" in names
    assert "timing" in names
    assert "duration" in names
    assert "claimed normal labs" in names
    result = orchestrate(FIXTURE, prior_facts={}, asked=[], answered=set())
    assert result.action.type == "ask_question"
    assert result.action.question_id == "q_laterality"
    assert result.safety_status == "S2"
    assert result.discovery_can_continue is True
    assert "you have" not in result.message.lower()
    assert "you have small-fiber" not in result.message.lower()
    assert "small-fiber neuropathy" not in result.message.lower()
    assert result.hypotheses  # families identified internally
    assert "laterality" in " ".join(result.unknowns)


def test_opening_does_not_dump_a_differential():
    result = orchestrate(FIXTURE, prior_facts={}, asked=[], answered=set())
    assert "worth investigating:" not in result.message.lower()
    assert result.interaction is not None
    assert result.interaction["type"] == "single_select"
    assert "Both" in result.interaction["options"]


def test_sudden_weakness_overrides_discovery():
    text = "It started this morning and now I can't lift my right foot."
    assert screen_safety(text).status == "S4"
    result = orchestrate(text, prior_facts={}, asked=[], answered=set())
    assert result.action.type == "show_safety_message"
    assert result.stage == "safety_triage"
    assert "urgent" in result.message.lower()
    assert "you have" not in result.message.lower()


def test_laterality_answer_advances_to_distribution():
    first = orchestrate(FIXTURE, prior_facts={}, asked=[], answered=set())
    prior = {item.name: item.value or "reported" for item in first.new_findings}
    second = orchestrate(
        "Both, but the right is worse.",
        prior_facts=prior,
        asked=["q_laterality"],
        answered={"laterality"},
        current_closes="laterality",
    )
    assert any(item.name == "laterality" for item in second.new_findings)
    assert second.action.question_id != "q_laterality"
    assert second.action.type in {"ask_question", "ask_question_group"}
    assert "you have" not in second.message.lower()


def test_laterality_contradiction_clarifies():
    result = orchestrate(
        "Both feet burn most nights.",
        prior_facts={"laterality": "right", "burning sensation": "reported", "location": "feet"},
        asked=["q_laterality"],
        answered={"laterality"},
    )
    assert result.action.type == "clarify"
    assert "laterality" in " ".join(result.contradictions)
    assert "both" in result.message.lower()
    assert "right" in result.message.lower()


def test_unknown_is_stored_and_not_reasked():
    result = orchestrate(
        "I don't know.",
        prior_facts={"burning sensation": "reported", "location": "feet", "laterality": "bilateral"},
        asked=["q_temperature"],
        answered=set(),
        current_closes="temperature sensation",
    )
    assert "uncertainty" in result.intents
    assert result.action.question_id != "q_temperature"


def test_reported_emg_requests_the_record():
    result = orchestrate(
        "Yes. It was normal.",
        prior_facts={
            "burning sensation": "reported",
            "location": "feet",
            "laterality": "bilateral",
            "distribution": "distal",
        },
        asked=["q_emg"],
        answered={"laterality", "distribution"},
        current_closes="emg_status",
    )
    assert result.action.type == "request_record"
    assert result.interaction is not None
    assert result.interaction["type"] == "file_upload"


def test_problem_representation_is_editable_prose():
    facts = {
        "duration": "about 6 months",
        "burning sensation": "reported",
        "location": "feet",
        "timing": "nighttime",
    }
    text = problem_representation(facts)
    assert "6 months" in text
    assert "burning" in text.lower()
    assert "laterality unknown" in text.lower()
    assert "neuropathy" not in text.lower()


def test_abdominal_problem_representation_keeps_felt_sensations():
    text = problem_representation(
        {
            "abdominal_pain": "location_unclear",
            "nausea": "reported",
            "fatty_food": "tolerated",
            "trajectory": "intermittent_stable",
            "fever": "absent",
            "vomiting": "absent",
            "patient_interpretation": "biliary_source",
        }
    )
    lowered = text.lower()
    assert "nausea" in lowered
    assert "fat" in lowered or "fatty" in lowered
    assert "intermittent" in lowered
    assert "laterality" not in lowered
    assert "weakness" not in lowered
    assert "theory" in lowered or "interpretation" in lowered
    assert "cholecystitis" not in lowered


def test_intake_findings_survive_as_drafts():
    result = orchestrate(FIXTURE, prior_facts={}, asked=[], answered=set())
    assert all(isinstance(item, FindingDraft) for item in result.new_findings)
    assert all(item.source == "intake" for item in result.new_findings)
