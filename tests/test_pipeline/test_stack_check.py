from __future__ import annotations

import pytest
from app.pipeline.stack_check import evaluate_stack

pytestmark = pytest.mark.unit


def test_ryr_on_statin_is_hold():
    out = evaluate_stack(labs=[{"name": "LDL", "value": 162, "unit": "mg/dL"}], stack=["Red yeast rice", "Berberine"], medications=["Crestor"])
    by_name = {row["name"]: row["verdict"] for row in out["verdicts"]}
    assert by_name["Red yeast rice"] == "hold"


def test_goldenseal_does_not_inherit_berberine():
    out = evaluate_stack(labs=[{"name": "LDL", "value": 190, "unit": "mg/dL"}], stack=["Goldenseal"])
    assert out["verdicts"][0]["verdict"] in {"hold", "mismatch"}
    assert "berberine" in out["verdicts"][0]["reason"].lower()


def test_psyllium_is_food_first_on_high_ldl():
    out = evaluate_stack(labs=[{"name": "LDL", "value": 170, "unit": "mg/dL"}], stack=["Psyllium"])
    assert out["verdicts"][0]["verdict"] == "food_first"


def test_normal_panel_mismatches_berberine():
    out = evaluate_stack(labs=[{"name": "LDL", "value": 90, "unit": "mg/dL"}, {"name": "HbA1c", "value": 5.2, "unit": "%"}], stack=["Berberine"])
    assert out["verdicts"][0]["verdict"] == "mismatch"
