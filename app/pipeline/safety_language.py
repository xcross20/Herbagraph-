"""Same safety fact, two audiences. Consumer text may not instruct a dose or call the unknown safe."""

from __future__ import annotations

CONSUMER = "consumer"
CLINICIAN = "clinician"

_CONSUMER_BY_REF = {
    "statin_analogue": (
        "Do not combine this with a statin. Ask your clinician before using it. "
        "This check does not tell you to stop a prescribed medicine."
    ),
    "pregnancy_hold": "Do not use this during pregnancy unless the clinician managing that pregnancy says otherwise.",
    "liver_caution": "A liver test on this panel is outside the usual range. Do not start this until a clinician reviews that result.",
    "glucose_lowering_overlap": "A glucose-lowering medicine is already listed. Do not add this until your clinician reviews both.",
    "current medications": "The medication list is missing. This check cannot treat that as safe.",
    "pregnancy status": "Pregnancy status is missing. This check cannot treat that as safe.",
    "unrecognized medication": "A listed medication is not one this check recognizes. Unrecognized is not the same as safe.",
    "exact form or species": "The exact product is not identified. Someone else's evidence is not applied to it.",
}

_CLINICIAN_BY_REF = {
    "statin_analogue": (
        "Monacolin K in red yeast rice is a statin-class analogue. "
        "Hold the combination with an active statin. This is not a dose change."
    ),
    "pregnancy_hold": "Hold in pregnancy. Do not convert this into a prenatal dosing instruction.",
    "liver_caution": (
        "Hepatic marker is outside range. Cassia is coumarin-bearing; red yeast rice carries statin-class hepatic risk. "
        "Hold pending ALT, AST, or GGT review."
    ),
    "glucose_lowering_overlap": "Hold berberine alongside an active glucose-lowering medicine. Review the regimen; do not stack doses here.",
    "current medications": "Medication list was not supplied. Do not document the combination as safe.",
    "pregnancy status": "Pregnancy status was not supplied. Do not document use as safe.",
    "unrecognized medication": "A medication string is outside the known statin and glucose-lowering lists. Do not treat it as non-interacting.",
    "exact form or species": "Form or species is unknown. Do not inherit a named form's evidence.",
}


def known_phrase_ref(ref: str | None) -> bool:
    """True when this key has a consumer sentence and a clinician sentence."""
    return bool(ref) and ref in _CONSUMER_BY_REF and ref in _CLINICIAN_BY_REF


def _ref(row: dict) -> str | None:
    for key in ("safety_refs", "missing_information"):
        values = row.get(key) or []
        if values:
            return values[0]
    return None


def phrase_for_audience(row: dict, audience: str) -> str:
    """Wording only. The verdict code is decided elsewhere and is not changed here."""
    ref = _ref(row)
    table = _CLINICIAN_BY_REF if audience == CLINICIAN else _CONSUMER_BY_REF
    if ref == "liver_caution" and audience == CLINICIAN:
        if row.get("code") == "cinnamon_cassia":
            return "Hepatic marker is outside range. Cassia is coumarin-bearing. Hold pending ALT, AST, or GGT review."
        if row.get("code") == "red_yeast_rice":
            return "Hepatic marker is outside range. Red yeast rice carries statin-class hepatic risk. Hold pending ALT, AST, or GGT review."
    if ref and ref in table:
        return table[ref]
    if audience == CLINICIAN:
        return row["reason"]
    if row["verdict"] == "discuss":
        return f"{row['name']} matches a lab pattern. Discuss it with a clinician. This is not an instruction to start it."
    if row["verdict"] == "food_first":
        return f"{row['name']} is a food to discuss for this lab pattern. It is not a pill and not a prescription."
    if row["verdict"] == "mismatch":
        return "These labs do not show the pattern this item is used for. That is not an instruction to take it."
    return row["reason"]


def present_verdict(row: dict, audience: str) -> dict:
    shown = dict(row)
    shown["fact_reason"] = row["reason"]
    shown["audience"] = audience
    shown["reason"] = phrase_for_audience(row, audience)
    return shown
