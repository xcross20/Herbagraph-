"""LLM may propose allow-listed facts and wording. It may not diagnose."""

from app.discovery.ai import (
    ALLOWED_FACT_NAMES,
    critic_allows,
    discovery_llm_ready,
    is_denied_concept,
    merge_llm_facts,
    pick_verbalization,
)
from app.discovery.intake import ExtractedFact
from app.discovery.orchestrator import orchestrate


FIXTURE = (
    "For six months, my feet have burned at night. My doctor says my blood work is normal."
)


def test_critic_blocks_diagnosis_copy():
    assert critic_allows("I can organize this as an investigation. Is it both feet?")
    assert not critic_allows("You have small-fiber neuropathy.")
    assert not critic_allows("This confirms diabetic neuropathy.")
    assert not critic_allows("You have diabetes.")


def test_verbalization_falls_back_when_critic_fails():
    fallback = "I can help organize this. Is the burning in both feet?"
    assert pick_verbalization(fallback, None) == fallback
    assert pick_verbalization(fallback, "You have small-fiber neuropathy.") == fallback
    assert pick_verbalization(fallback, "short") == fallback
    kept = pick_verbalization(fallback, "Is the burning usually in both feet, or mainly one?")
    assert "both feet" in kept.lower()


def test_llm_facts_keep_allow_list_only():
    base = [ExtractedFact(name="burning sensation", value="reported", kind="symptom")]
    merged = merge_llm_facts(
        base,
        [
            {"name": "laterality", "value": "bilateral"},
            {"name": "small-fiber neuropathy", "value": "diagnosed"},
            {"name": "diagnosis", "value": "SFN"},
            {"name": "burning sensation", "value": "severe"},
        ],
    )
    names = [item.name for item in merged]
    assert "laterality" in names
    assert "small-fiber neuropathy" not in names
    assert "diagnosis" not in names
    assert names.count("burning sensation") == 1
    assert merged[0].value == "reported"


def test_deny_list_uses_word_boundaries():
    assert is_denied_concept("trigeminal neuralgia")
    assert is_denied_concept("You have diabetes")
    assert not is_denied_concept("right-sided facial pressure")
    assert not is_denied_concept("tumorigenesis panel")
    assert not is_denied_concept("gallbladder")


def test_merge_keeps_multiple_patient_interpretations():
    merged = merge_llm_facts(
        [],
        [
            {"name": "patient_interpretation", "value": "maybe gallbladder", "kind": "context"},
            {"name": "patient_interpretation", "value": "maybe related to shock", "kind": "context"},
        ],
        allow_open=True,
    )
    values = {item.value for item in merged}
    assert "maybe gallbladder" in values
    assert "maybe related to shock" in values
    assert len(merged) == 2


def test_allow_list_does_not_include_diseases():
    blob = " ".join(ALLOWED_FACT_NAMES)
    assert "neuropathy" not in blob
    assert "diabetes" not in blob
    assert "laterality" in ALLOWED_FACT_NAMES


def test_orchestrator_ignores_off_list_llm_facts():
    result = orchestrate(
        FIXTURE,
        prior_facts={},
        asked=[],
        answered=set(),
        llm_fact_rows=[{"name": "small-fiber neuropathy", "value": "diagnosed"}],
    )
    assert result.action.question_id == "q_laterality"
    assert all(item.name != "small-fiber neuropathy" for item in result.new_findings)
    assert "you have" not in result.message.lower()


def test_orchestrator_discards_diagnosis_verbalization():
    result = orchestrate(
        FIXTURE,
        prior_facts={},
        asked=[],
        answered=set(),
        llm_message="You have small-fiber neuropathy based on this story.",
    )
    assert result.action.question_id == "q_laterality"
    assert "you have" not in result.message.lower()
    assert "small-fiber neuropathy" not in result.message.lower()


def test_test_api_key_does_not_enable_discovery_llm(monkeypatch):
    monkeypatch.setattr("app.pipeline.llm_client.llm_configured", lambda: True)
    monkeypatch.setattr("app.pipeline.llm_client.llm_api_key", lambda: "test-openai-api-key")
    assert discovery_llm_ready() is False


def test_missing_key_does_not_enable_discovery_llm(monkeypatch):
    monkeypatch.setattr("app.pipeline.llm_client.llm_configured", lambda: False)
    assert discovery_llm_ready() is False
