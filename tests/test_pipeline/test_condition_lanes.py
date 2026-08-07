"""Condition-aligned report lanes — separate from lab priority scoring."""

import pytest

from app.pipeline.condition_lanes import build_condition_aligned

pytestmark = pytest.mark.unit


def test_empty_without_conditions():
    payload = build_condition_aligned({"known_conditions": []}, {"measured_biomarkers": []})
    assert payload["empty"] is True
    assert payload["items"] == []
    assert payload["model"] == "condition_lanes_v1"


def test_hypertension_lane_has_dash_and_licorice_caution():
    payload = build_condition_aligned(
        {
            "known_conditions": ["hypertension"],
            "current_medications": ["lisinopril"],
        },
        {
            "measured_biomarkers": [
                {"biomarker_name": "Creatinine", "status": "normal"},
                {"biomarker_name": "Potassium", "status": "high"},
                {"biomarker_name": "Iron", "status": "low"},
            ]
        },
    )
    assert payload["empty"] is False
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["condition_key"] == "hypertension"
    titles = [c["title"] for c in item["considerations"]]
    assert any("DASH" in t for t in titles)
    assert any("licorice" in t.lower() or "glycyrrhizin" in t.lower() for t in titles)
    # Lab overlap includes related markers, not Iron (iron not on HTN watchlist)
    overlap_names = {m["biomarker_name"] for m in item["lab_overlap"]}
    assert "Creatinine" in overlap_names
    assert "Potassium" in overlap_names
    assert "Iron" not in overlap_names
    # Potassium flagged abnormal
    pot = next(m for m in item["lab_overlap"] if m["biomarker_name"] == "Potassium")
    assert pot["abnormal"] is True
    # Meds attached to medication_review consideration
    med_c = next(c for c in item["considerations"] if c.get("kind") == "medication_review")
    assert "lisinopril" in med_c.get("related_medications", [])


def test_high_blood_pressure_phrase_matches():
    payload = build_condition_aligned({"known_conditions": ["High blood pressure"]})
    assert payload["empty"] is False
    assert payload["items"][0]["condition_key"] == "hypertension"


def test_diabetes_lane():
    payload = build_condition_aligned(
        {"known_conditions": ["type 2 diabetes"]},
        {
            "measured_biomarkers": [
                {"biomarker_name": "Glucose", "status": "high"},
                {"biomarker_name": "HbA1c", "status": "high"},
            ]
        },
    )
    assert payload["empty"] is False
    item = payload["items"][0]
    assert item["condition_key"] == "diabetes"
    assert any(m["biomarker_name"] == "Glucose" for m in item["lab_overlap"])


def test_pregnancy_safety_first():
    payload = build_condition_aligned({"known_conditions": ["pregnancy, first trimester"]})
    assert payload["empty"] is False
    item = payload["items"][0]
    assert item["condition_key"] == "pregnancy"
    kinds = {c["kind"] for c in item["considerations"]}
    assert "safety_caution" in kinds


def test_unmapped_condition_listed():
    payload = build_condition_aligned({"known_conditions": ["migraine with aura"]})
    assert payload["empty"] is True
    assert "migraine with aura" in payload["unmapped_conditions"]


def test_does_not_invent_lab_priorities():
    """Condition lanes must not expose clinical_priority_score fields."""
    payload = build_condition_aligned({"known_conditions": ["hypertension", "diabetes"]})
    for item in payload["items"]:
        assert "clinical_priority_score" not in item
        for c in item["considerations"]:
            assert "clinical_priority_score" not in c
            assert "priority_score" not in c
