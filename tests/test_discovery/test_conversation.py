"""Discovery conversation is one question per turn, never a diagnosis."""

from app.discovery.conversation import compose_system_reply, parse_turn_answer
from app.discovery.engine import rebuild_case_state
from app.models.enums import LabResultStatus
from app.schemas.pipeline import NormalizedLabResult


def _lab(name: str, value: float, status: LabResultStatus) -> NormalizedLabResult:
    return NormalizedLabResult(
        biomarker_name=name,
        raw_test_name=name,
        value=value,
        unit="",
        status=status,
        category=None,
    )


def test_parse_turn_answer_only_accepts_whole_message():
    assert parse_turn_answer("Yes") == "yes"
    assert parse_turn_answer("not sure.") == "unknown"
    assert parse_turn_answer("yes I also have tingling") is None


def test_system_reply_asks_exactly_one_question():
    snapshot = rebuild_case_state(
        "burning feet at night",
        [
            _lab("Vitamin B12", 210, LabResultStatus.LOW),
            _lab("MCV", 104, LabResultStatus.HIGH),
        ],
        {},
    )
    text, code = compose_system_reply(snapshot)
    assert snapshot.next_questions
    assert code == snapshot.next_questions[0].code
    assert snapshot.next_questions[0].prompt in text
    assert text.count("?") == 1
    assert "not a diagnosis" in text.lower()
    for extra in snapshot.next_questions[1:]:
        assert extra.prompt not in text
