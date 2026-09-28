"""Stack Check gold cases. Expectations come from the identity rules, not from the engine's output."""

from __future__ import annotations

import pytest

from app.pipeline.stack_verdicts import DISCUSS, FOOD_FIRST, HOLD, MISMATCH, UNKNOWN, evaluate_stack

pytestmark = pytest.mark.unit


def _by_code(out: dict) -> dict[str, dict]:
    return {row["code"]: row for row in out["verdicts"]}


def test_crestor_plus_red_yeast_rice_is_hold():
    out = evaluate_stack(
        labs=[{"name": "LDL", "value": 162, "unit": "mg/dL"}],
        stack=["Red yeast rice"],
        medications=["Crestor"],
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == HOLD
    assert "monacolin" in row["reason"].lower()
    assert "statin_analogue" in row["safety_refs"]


def test_goldenseal_cannot_inherit_berberine():
    out = evaluate_stack(
        labs=[{"name": "LDL", "value": 190, "unit": "mg/dL"}],
        stack=["Goldenseal"],
        medications=[],
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == MISMATCH
    assert row["code"] == "goldenseal"
    assert "berberine" in row["reason"].lower()
    assert "does_not_address:berberine" in row["evidence_refs"]


def test_psyllium_on_high_ldl_is_food_first():
    out = evaluate_stack(
        labs=[{"name": "LDL", "value": 170, "unit": "mg/dL"}],
        stack=["Psyllium"],
        medications=[],
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == FOOD_FIRST
    assert row["code"] == "psyllium_husk"


def test_normal_panel_mismatches_berberine():
    out = evaluate_stack(
        labs=[
            {"name": "LDL", "value": 90, "unit": "mg/dL"},
            {"name": "HbA1c", "value": 5.2, "unit": "%"},
        ],
        stack=["Berberine"],
        medications=[],
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == MISMATCH
    assert row["code"] == "berberine"


def test_bare_cinnamon_stays_unknown_even_with_high_glucose():
    out = evaluate_stack(
        labs=[{"name": "Glucose", "value": 140, "unit": "mg/dL"}],
        stack=["cinnamon"],
        medications=[],
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == UNKNOWN
    assert row["code"] == "unknown_cinnamon_product"
    assert row["verdict"] != DISCUSS


def test_cassia_with_high_alt_is_hold_and_ceylon_is_not():
    labs = [
        {"name": "Glucose", "value": 140, "unit": "mg/dL"},
        {"name": "ALT", "value": 80, "unit": "U/L"},
    ]
    out = evaluate_stack(labs=labs, stack=["cassia", "ceylon cinnamon"], medications=[], conditions=[])
    by_code = _by_code(out)
    assert by_code["cinnamon_cassia"]["verdict"] == HOLD
    assert by_code["cinnamon_ceylon"]["verdict"] == DISCUSS


def test_missing_medications_does_not_clear_red_yeast_rice():
    out = evaluate_stack(
        labs=[{"name": "LDL", "value": 180, "unit": "mg/dL"}],
        stack=["Red yeast rice"],
        medications=None,
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == UNKNOWN
    assert "current medications" in row["missing_information"]


def test_berberine_with_metformin_is_hold():
    out = evaluate_stack(
        labs=[{"name": "HbA1c", "value": 7.1, "unit": "%"}],
        stack=["Berberine"],
        medications=["metformin"],
        conditions=[],
    )
    row = out["verdicts"][0]
    assert row["verdict"] == HOLD
    assert "glucose_lowering_overlap" in row["safety_refs"]


def test_berberine_in_pregnancy_is_hold():
    out = evaluate_stack(
        labs=[{"name": "Glucose", "value": 130, "unit": "mg/dL"}],
        stack=["Berberine"],
        medications=[],
        conditions=["pregnant"],
    )
    assert out["verdicts"][0]["verdict"] == HOLD
