"""Guided Discovery engine: relevance is not diagnosis."""

from app.discovery.engine import rebuild_case_state
from app.models.enums import LabResultStatus
from app.schemas.pipeline import NormalizedLabResult


def _lab(name: str, value: float, status: LabResultStatus, unit: str = "") -> NormalizedLabResult:
    return NormalizedLabResult(
        biomarker_name=name,
        raw_test_name=name,
        value=value,
        unit=unit,
        status=status,
        category=None,
    )


def test_burning_feet_with_b12_is_relevant_not_diagnosed():
    snapshot = rebuild_case_state(
        "For six months my feet have burned at night. My doctor says blood work is normal.",
        [
            _lab("Vitamin B12", 210, LabResultStatus.LOW, "pg/mL"),
            _lab("MCV", 104, LabResultStatus.HIGH, "fL"),
        ],
        {},
    )
    codes = {item.code for item in snapshot.hypotheses}
    assert "small_fiber_dysfunction" in codes
    assert "b12_functional_gap" in codes
    b12 = next(item for item in snapshot.hypotheses if item.code == "b12_functional_gap")
    assert b12.investigation_relevance > b12.diagnostic_certainty
    assert b12.diagnostic_certainty < 0.73
    assert "MMA" in b12.missing_markers
    assert any(item.group == "core" for item in b12.investigations)
    assert any(item.group == "directed" for item in b12.investigations)
    assert any(item.group == "conditional" for item in b12.investigations)
    assert snapshot.investigation_coverage < 1.0
    assert snapshot.monitor_plan
    assert any("MMA" in item.label for item in snapshot.monitor_plan)
    assert snapshot.next_questions
    assert any("MMA" in q.prompt or "methylmalonic" in q.prompt.lower() for q in snapshot.next_questions)
    nutritional = next(row for row in snapshot.branch_coverage if row.branch == "nutritional")
    assert 0 < nutritional.coverage < 1
    assert "diagnosis" in snapshot.disclaimer.lower() or "not a diagnosis" in snapshot.disclaimer.lower()


def test_empty_case_has_no_fake_diagnosis():
    snapshot = rebuild_case_state("   ", [], {})
    assert snapshot.hypotheses == []
    assert snapshot.investigation_coverage == 0
    assert snapshot.findings == []


def test_concern_without_labs_has_low_certainty():
    snapshot = rebuild_case_state("burning feet at night", [], {})
    assert snapshot.hypotheses
    for item in snapshot.hypotheses:
        assert item.diagnostic_certainty < 0.40
        assert item.status == "open"
        assert item.investigation_relevance >= item.diagnostic_certainty


def test_answered_mma_is_no_longer_missing():
    snapshot = rebuild_case_state(
        "burning feet at night",
        [
            _lab("Vitamin B12", 210, LabResultStatus.LOW, "pg/mL"),
            _lab("MCV", 104, LabResultStatus.HIGH, "fL"),
        ],
        {},
        extra_assessed=["MMA"],
        answered_labels=["MMA"],
    )
    b12 = next(item for item in snapshot.hypotheses if item.code == "b12_functional_gap")
    assert "MMA" not in b12.missing_markers
    assert not any(q.closes == "MMA" for q in snapshot.next_questions)
    assert snapshot.investigation_coverage > 0


def test_snapshot_roundtrip():
    snapshot = rebuild_case_state(
        "fatigue and hair loss",
        [_lab("Ferritin", 12, LabResultStatus.LOW, "ng/mL")],
        {"age_range": "30-39"},
    )
    restored = snapshot.from_dict(snapshot.as_dict())
    assert restored.presenting_concern == snapshot.presenting_concern
    assert len(restored.hypotheses) == len(snapshot.hypotheses)
    assert restored.hypotheses[0].code == snapshot.hypotheses[0].code
    assert len(restored.monitor_plan) == len(snapshot.monitor_plan)
