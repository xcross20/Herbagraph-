"""Common conditions library for matrix UI + safety mapping."""

import pytest

from app.knowledge_graph.common_conditions import (
    COMMON_CONDITIONS,
    list_common_conditions,
    match_common_condition_keys,
    other_conditions_not_in_library,
    safety_keys_for_known_conditions,
)
from app.safety_engine.condition_catalog import active_conditions

pytestmark = pytest.mark.unit


def test_library_has_near_100_conditions():
    assert len(COMMON_CONDITIONS) >= 80
    assert len(list_common_conditions()) == len(COMMON_CONDITIONS)


def test_library_entries_have_required_fields():
    keys = set()
    for e in COMMON_CONDITIONS:
        assert e["key"]
        assert e["label"]
        assert e["category"]
        assert e["key"] not in keys
        keys.add(e["key"])


def test_matrix_labels_map_to_safety_keys():
    keys = safety_keys_for_known_conditions(
        ["Hypertension", "Type 2 diabetes", "Chronic kidney disease", "Currently pregnant"]
    )
    assert "hypertension" in keys
    assert "diabetes" in keys
    assert "kidney_disease" in keys
    assert "pregnancy" in keys


def test_active_conditions_includes_library_mapping():
    active = active_conditions(["Type 2 diabetes", "NAFLD / fatty liver"])
    assert "diabetes" in active
    assert "liver_disease" in active


def test_other_free_text_preserved():
    known = ["Hypertension", "Ehlers-Danlos syndrome"]
    other = other_conditions_not_in_library(known)
    assert "Ehlers-Danlos syndrome" in other
    assert not any("hypertension" in o.lower() for o in other)


def test_short_alias_does_not_overmatch():
    # "ms" alone should not light up every condition
    matched = match_common_condition_keys(["ms"])
    # Multiple sclerosis has alias "ms" as exact alias — exact match on alias is OK
    assert matched <= {"multiple_sclerosis"}
