"""The report repeats the stored verdict and changes only the words."""

from __future__ import annotations

import uuid

import pytest

from app.pipeline.consumer_report import build_case_report

pytestmark = pytest.mark.unit


class _Finding:
    def __init__(self, **kwargs):
        self.active = True
        self.source = "stack_check"
        self.kind = "context"
        self.branch = None
        self.source_event_id = "stack_check"
        self.status = None
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_stored_hold_keeps_its_code_and_hides_the_mechanism():
    case_id = uuid.uuid4()
    report = build_case_report(
        case_id=case_id,
        audience="consumer",
        findings=[
            _Finding(
                name="Red yeast rice",
                value="hold",
                status="hold",
                branch="red_yeast_rice",
                source_event_id="stack_check:statin_analogue",
            )
        ],
    )
    assert report["audience"] == "consumer"
    assert report["items"] == [{
        "name": "Red yeast rice",
        "verdict": "hold",
        "text": (
            "Do not combine this with a statin. Ask your clinician before using it. "
            "This check does not tell you to stop a prescribed medicine."
        ),
    }]
    assert "monacolin" not in report["items"][0]["text"].lower()
    assert "mg" not in report["items"][0]["text"].lower()
    assert "is safe" not in report["items"][0]["text"].lower()


def test_clinician_words_change_and_the_verdict_does_not():
    finding = _Finding(
        name="Red yeast rice",
        value="hold",
        branch="red_yeast_rice",
        source_event_id="stack_check:statin_analogue",
    )
    consumer = build_case_report(case_id=uuid.uuid4(), audience="consumer", findings=[finding])
    clinician = build_case_report(case_id=uuid.uuid4(), audience="clinician", findings=[finding])
    assert consumer["items"][0]["verdict"] == clinician["items"][0]["verdict"] == "hold"
    assert "monacolin" not in consumer["items"][0]["text"].lower()
    assert "monacolin" in clinician["items"][0]["text"].lower()


def test_missing_fact_is_not_called_safe_and_a_stray_word_is_dropped():
    report = build_case_report(
        case_id=uuid.uuid4(),
        audience="consumer",
        findings=[
            _Finding(name="Red yeast rice", value="unknown", source_event_id="stack_check:current medications"),
            _Finding(name="Mystery", value="cured", source_event_id="stack_check"),
            _Finding(name="Burning feet", value="six months", source="user", kind="symptom"),
        ],
    )
    assert [item["name"] for item in report["items"]] == ["Red yeast rice"]
    assert report["items"][0]["verdict"] == "unknown"
    assert "cannot treat that as safe" in report["items"][0]["text"]
    assert "is safe" not in report["items"][0]["text"].lower()
    assert "not the same as safe" in report["disclaimer"]
    assert "caused" not in report["disclaimer"]


def test_a_hold_without_a_ref_does_not_invent_a_mechanism():
    report = build_case_report(
        case_id=uuid.uuid4(),
        audience="consumer",
        findings=[_Finding(name="Red yeast rice", value="hold", source_event_id="stack_check")],
    )
    text = report["items"][0]["text"].lower()
    assert "on hold" in text
    assert "monacolin" not in text
    assert "stop your statin" not in text
    assert "is safe" not in text


def test_lab_lines_do_not_become_a_cause():
    report = build_case_report(
        case_id=uuid.uuid4(),
        audience="consumer",
        findings=[
            _Finding(kind="lab", name="LDL", value="162.0", status="high"),
            _Finding(kind="lab", name="HbA1c", value="5.2", status="optimal"),
        ],
    )
    assert report["items"] == []
    assert report["labs"][0]["text"] == "LDL is outside the usual range."
    assert report["labs"][1]["text"] == "HbA1c is inside the usual range."
    blob = " ".join(row["text"] for row in report["labs"]).lower()
    assert "mg" not in blob
    assert "caused" not in blob
