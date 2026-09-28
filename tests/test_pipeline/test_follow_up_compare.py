"""A later lab can move closer or farther. The movement is not a cause."""

from __future__ import annotations

import pytest

from app.pipeline.follow_up_compare import compare_lab_rows

pytestmark = pytest.mark.unit


def test_ldl_moving_closer_is_not_a_cause():
    report = compare_lab_rows(
        [{"name": "LDL", "value": 162, "unit": "mg/dL"}],
        [{"name": "LDL", "value": 140, "unit": "mg/dL"}],
        "consumer",
    )
    change = report["changes"][0]
    assert change["direction"] == "improved"
    assert "162" in change["text"] and "140" in change["text"]
    assert "not proof that a supplement produced the change" in change["text"]
    assert "caused" not in change["text"].lower()
    assert "mg" not in change["text"].lower()
    blob = str(report).lower()
    assert "berberine" not in blob
    assert "intervention" not in blob


def test_a_lower_ferritin_can_be_farther_from_the_range():
    report = compare_lab_rows(
        [{"name": "Ferritin", "value": 30, "unit": "ng/mL"}],
        [{"name": "Ferritin", "value": 15, "unit": "ng/mL"}],
        "consumer",
    )
    change = report["changes"][0]
    assert change["follow_up_value"] < change["baseline_value"]
    assert change["direction"] == "worsened"
    assert "farther" in change["text"]
    assert "closer" not in change["text"]


def test_a_missing_later_value_is_not_recorded_as_unchanged():
    report = compare_lab_rows(
        [
            {"name": "LDL", "value": 162, "unit": "mg/dL"},
            {"name": "HbA1c", "value": 5.2, "unit": "%"},
        ],
        [{"name": "LDL", "value": 162, "unit": "mg/dL"}],
        "consumer",
    )
    assert report["changes"][0]["direction"] == "unchanged"
    assert "not proof that a supplement had no effect" in report["changes"][0]["text"]
    assert report["missing"] == [{
        "name": "HbA1c",
        "side": "follow_up",
        "text": "HbA1c is missing from the later panel. Missing is not the same as no change.",
    }]
    assert "unchanged" not in report["missing"][0]["text"]


def test_clinician_words_keep_the_same_direction():
    consumer = compare_lab_rows(
        [{"name": "LDL", "value": 90, "unit": "mg/dL"}],
        [{"name": "LDL", "value": 170, "unit": "mg/dL"}],
        "consumer",
    )
    clinician = compare_lab_rows(
        [{"name": "LDL", "value": 90, "unit": "mg/dL"}],
        [{"name": "LDL", "value": 170, "unit": "mg/dL"}],
        "clinician",
    )
    assert consumer["changes"][0]["direction"] == clinician["changes"][0]["direction"] == "worsened"
    assert "Not a causal attribution." in clinician["changes"][0]["text"]
    assert "caused" not in clinician["changes"][0]["text"].lower()
