"""Same hold or unknown fact. Consumer wording must not become a dosing instruction or a safety clearance."""

from __future__ import annotations

import pytest

from app.pipeline.safety_language import CLINICIAN, CONSUMER, present_verdict
from app.pipeline.stack_verdicts import HOLD, UNKNOWN, evaluate_stack

pytestmark = pytest.mark.unit

_HIGH_LDL = [{"name": "LDL", "value": 180, "unit": "mg/dL"}]
_HIGH_GLUCOSE = [{"name": "Glucose", "value": 140, "unit": "mg/dL"}]
_HIGH_ALT = [{"name": "ALT", "value": 80, "unit": "U/L"}, {"name": "LDL", "value": 180, "unit": "mg/dL"}]
_HIGH_ALT_GLUCOSE = [{"name": "ALT", "value": 80, "unit": "U/L"}, {"name": "Glucose", "value": 140, "unit": "mg/dL"}]


def _one(**kwargs) -> dict:
    out = evaluate_stack(**kwargs)
    return out["verdicts"][0]


def _both(row: dict) -> tuple[dict, dict]:
    return present_verdict(row, CONSUMER), present_verdict(row, CLINICIAN)


def test_statin_and_red_yeast_rice_hold_in_both_voices():
    row = _one(labs=_HIGH_LDL, stack=["Red yeast rice"], medications=["Crestor"], conditions=[])
    consumer, clinician = _both(row)
    assert consumer["verdict"] == clinician["verdict"] == HOLD
    assert "stop your statin" not in consumer["reason"].lower()
    assert "mg" not in consumer["reason"].lower()
    assert "monacolin" in clinician["reason"].lower()


def test_pregnancy_and_berberine_hold_in_both_voices():
    row = _one(labs=_HIGH_GLUCOSE, stack=["Berberine"], medications=[], conditions=["pregnant"])
    consumer, clinician = _both(row)
    assert consumer["verdict"] == clinician["verdict"] == HOLD
    assert "do not use this during pregnancy" in consumer["reason"].lower()


def test_hepatic_abnormality_holds_red_yeast_rice_and_cassia():
    ryr = _one(labs=_HIGH_ALT, stack=["Red yeast rice"], medications=[], conditions=[])
    cassia = _one(labs=_HIGH_ALT_GLUCOSE, stack=["cassia"], medications=[], conditions=[])
    assert ryr["verdict"] == HOLD
    assert cassia["verdict"] == HOLD
    assert "liver_caution" in ryr["safety_refs"]
    assert "liver_caution" in cassia["safety_refs"]
    consumer, clinician = _both(cassia)
    assert consumer["verdict"] == clinician["verdict"]
    assert "coumarin" not in consumer["reason"].lower()
    assert "coumarin" in clinician["reason"].lower()


def test_glucose_medicine_and_berberine_hold():
    row = _one(labs=_HIGH_GLUCOSE, stack=["Berberine"], medications=["metformin"], conditions=[])
    consumer, clinician = _both(row)
    assert consumer["verdict"] == clinician["verdict"] == HOLD
    assert "safe to" not in consumer["reason"].lower()


def test_missing_medication_list_is_not_safe():
    row = _one(labs=_HIGH_LDL, stack=["Red yeast rice"], medications=None, conditions=[])
    consumer, clinician = _both(row)
    assert consumer["verdict"] == clinician["verdict"] == UNKNOWN
    assert "current medications" in row["missing_information"]
    assert "is safe" not in consumer["reason"].lower()
    assert "cannot treat that as safe" in consumer["reason"].lower()


def test_unrecognized_medication_is_not_a_clearance():
    row = _one(labs=_HIGH_LDL, stack=["Red yeast rice"], medications=["aspirin"], conditions=[])
    consumer, _clinician = _both(row)
    assert row["verdict"] == UNKNOWN
    assert "unrecognized medication" in row["missing_information"]
    assert consumer["verdict"] == UNKNOWN
    assert "not the same as safe" in consumer["reason"].lower()
