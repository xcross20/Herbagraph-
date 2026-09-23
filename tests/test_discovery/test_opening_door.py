"""Ask opening-door classification — investigation stays the default for niche cases."""

from __future__ import annotations

import pytest

from app.discovery.intent import classify_opening_door

pytestmark = pytest.mark.unit


def test_burning_feet_is_investigation():
    text = "For six months, my feet have burned at night. My doctor says my blood work is normal."
    assert classify_opening_door(text) == "investigation"


def test_gallbladder_style_pain_is_investigation():
    text = "I've been dealing with this weird pain under my right ribs for eight months."
    assert classify_opening_door(text) == "investigation"


def test_labs_on_hand_without_symptom_story():
    assert classify_opening_door("I already have labs — take me to upload.") == "labs_on_hand"


def test_stack_eval_for_berberine_purchase():
    text = "I'm considering berberine and red yeast rice. I'm on Crestor."
    assert classify_opening_door(text) == "stack_eval"


def test_diagnosis_demand_is_not_investigation():
    assert classify_opening_door("What disease do I have?") == "diagnosis_demand"


def test_overlapping_symptoms_beat_stack_mention():
    text = (
        "Burning feet for a year, gallbladder pain, nobody knows what's going on. "
        "Someone told me to try berberine."
    )
    assert classify_opening_door(text) == "investigation"
