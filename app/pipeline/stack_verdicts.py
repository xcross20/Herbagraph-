"""Deterministic stack eligibility. No model ranking.

A verdict is hold, food_first, discuss, mismatch, or unknown.
Missing medication or pregnancy status is not treated as safe when that
fact would clear a safety gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.knowledge_graph.claim_contract import INDICATION_FAMILY_MARKERS
from app.models.enums import LabResultStatus
from app.pipeline.manual_labs import normalize_typed_rows
from app.pipeline.metabolic_identity import (
    clinical_flags,
    explicitly_does_not_address,
    resolve_metabolic_code,
)
from app.discovery.composition import concept, load_metabolic_graph, unknown_form_stays_unknown

HOLD = "hold"
FOOD_FIRST = "food_first"
DISCUSS = "discuss"
MISMATCH = "mismatch"
UNKNOWN = "unknown"

_ABNORMAL = frozenset({
    LabResultStatus.LOW,
    LabResultStatus.HIGH,
    LabResultStatus.CRITICAL_LOW,
    LabResultStatus.CRITICAL_HIGH,
})

_STATIN_NAMES = frozenset({
    "statin",
    "atorvastatin",
    "lipitor",
    "rosuvastatin",
    "crestor",
    "simvastatin",
    "zocor",
    "pravastatin",
    "lovastatin",
    "fluvastatin",
    "pitavastatin",
})

_GLUCOSE_LOWERING = frozenset({
    "metformin",
    "insulin",
    "glipizide",
    "glyburide",
    "glimepiride",
    "sitagliptin",
    "empagliflozin",
    "semaglutide",
    "ozempic",
})


@dataclass(frozen=True)
class StackVerdict:
    input: str
    code: str | None
    name: str
    verdict: str
    reason: str
    evidence_refs: tuple[str, ...]
    identity_refs: tuple[str, ...]
    safety_refs: tuple[str, ...]
    missing_information: tuple[str, ...]
    next_clarification: str | None

    def as_dict(self) -> dict:
        return asdict(self)


_DECLARED_NONE = frozenset({"none", "no", "n/a", "na", "no medications", "none reported"})


def _text_hits(values: list[str] | None, names: frozenset[str]) -> bool:
    blob = " ".join(values or []).lower()
    return any(name in blob for name in names)


def _known_medication(text: str) -> bool:
    blob = text.strip().lower()
    if blob in _DECLARED_NONE:
        return True
    return any(name in blob for name in _STATIN_NAMES | _GLUCOSE_LOWERING)


def _unrecognized_medications(medications: list[str] | None) -> tuple[str, ...]:
    if not medications:
        return ()
    return tuple(item for item in medications if not _known_medication(item))


def _abnormal_families(labs: list[dict]) -> set[str]:
    families: set[str] = set()
    for row in normalize_typed_rows(labs):
        if row.status not in _ABNORMAL:
            continue
        for family, markers in INDICATION_FAMILY_MARKERS.items():
            if row.biomarker_name in markers:
                families.add(family)
    return families


def _hepatic_abnormal(labs: list[dict]) -> bool:
    hepatic = INDICATION_FAMILY_MARKERS["hepatic"]
    return any(
        row.status in _ABNORMAL and row.biomarker_name in hepatic
        for row in normalize_typed_rows(labs)
    )


def _pregnant(conditions: list[str] | None) -> bool:
    blob = " ".join(conditions or []).lower()
    return "pregnan" in blob


def _verdict(
    *,
    raw: str,
    code: str | None,
    name: str,
    verdict: str,
    reason: str,
    evidence_refs: tuple[str, ...] = (),
    identity_refs: tuple[str, ...] = (),
    safety_refs: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
    next_clarification: str | None = None,
) -> StackVerdict:
    return StackVerdict(
        input=raw,
        code=code,
        name=name,
        verdict=verdict,
        reason=reason,
        evidence_refs=evidence_refs,
        identity_refs=identity_refs,
        safety_refs=safety_refs,
        missing_information=missing_information,
        next_clarification=next_clarification,
    )


def verdict_for_item(
    raw: str,
    *,
    labs: list[dict],
    medications: list[str] | None,
    conditions: list[str] | None,
) -> StackVerdict:
    code = resolve_metabolic_code(raw)
    graph = load_metabolic_graph()
    if code is None or unknown_form_stays_unknown(code, graph):
        label = (concept(code, graph) or {}).get("label", raw) if code else raw
        return _verdict(
            raw=raw,
            code=code,
            name=label,
            verdict=UNKNOWN,
            reason="The exact form is unknown, so no metabolic evidence is applied.",
            identity_refs=(code,) if code else (),
            missing_information=("exact form or species",),
            next_clarification="Name the species or the form on the product label.",
        )

    flags = clinical_flags(code)
    families = set(flags.get("indication_families") or [])
    active = _abnormal_families(labs)
    matched = families & active
    identity_refs = (code,)

    if explicitly_does_not_address(code, "berberine"):
        return _verdict(
            raw=raw,
            code=code,
            name=(concept(code, graph) or {}).get("label", raw),
            verdict=MISMATCH,
            reason="This is not berberine. Berberine lipid and glycemic papers do not transfer.",
            identity_refs=(code, "berberine"),
            evidence_refs=("does_not_address:berberine",),
        )

    name = (concept(code, graph) or {}).get("label", raw)
    meds_known = medications is not None
    conditions_known = conditions is not None
    on_statin = _text_hits(medications, _STATIN_NAMES)
    on_glucose_drug = _text_hits(medications, _GLUCOSE_LOWERING)
    liver = _hepatic_abnormal(labs)

    if flags.get("pregnancy_hold") and _pregnant(conditions):
        return _verdict(
            raw=raw, code=code, name=name, verdict=HOLD,
            reason=f"{name} is on hold in pregnancy.",
            identity_refs=identity_refs,
            safety_refs=("pregnancy_hold",),
            next_clarification="Discuss this with the clinician managing the pregnancy.",
        )
    if flags.get("pharmacologic_analogue") == "statin" and on_statin:
        return _verdict(
            raw=raw, code=code, name=name, verdict=HOLD,
            reason="Red yeast rice contains monacolin K, a statin-class analogue. Do not stack it on an active statin.",
            identity_refs=identity_refs + ("monacolin_k",),
            safety_refs=("statin_analogue",),
            evidence_refs=("contains_measured:monacolin_k",),
            next_clarification="Confirm the current statin dose before any monacolin-containing product.",
        )
    if flags.get("liver_caution") and liver:
        return _verdict(
            raw=raw, code=code, name=name, verdict=HOLD,
            reason="A hepatic marker on this panel is outside range, and this form carries a liver caution.",
            identity_refs=identity_refs,
            safety_refs=("liver_caution",),
            next_clarification="Review ALT, AST, or GGT before this item.",
        )
    if code == "berberine" and on_glucose_drug:
        return _verdict(
            raw=raw, code=code, name=name, verdict=HOLD,
            reason="Berberine is on hold while a glucose-lowering medicine is already in use.",
            identity_refs=identity_refs,
            safety_refs=("glucose_lowering_overlap",),
            next_clarification="Review the current glucose-lowering regimen before discussing berberine.",
        )

    if not matched:
        return _verdict(
            raw=raw, code=code, name=name, verdict=MISMATCH,
            reason="No abnormal marker on this panel matches this item's indication family.",
            identity_refs=identity_refs,
            evidence_refs=tuple(sorted(families)),
        )

    missing: list[str] = []
    medication_gate = flags.get("pharmacologic_analogue") == "statin" or code == "berberine"
    if medication_gate and _unrecognized_medications(medications):
        missing.append("unrecognized medication")
    if flags.get("pharmacologic_analogue") == "statin" and not meds_known:
        missing.append("current medications")
    if flags.get("pregnancy_hold") and not conditions_known:
        missing.append("pregnancy status")
    if missing:
        return _verdict(
            raw=raw, code=code, name=name, verdict=UNKNOWN,
            reason="The lab pattern matches, but a safety fact required for this item was not provided.",
            identity_refs=identity_refs,
            safety_refs=tuple(missing),
            missing_information=tuple(missing),
            next_clarification="Provide the missing safety fact before a discuss or food-first verdict.",
        )

    if flags.get("food_first"):
        return _verdict(
            raw=raw, code=code, name=name, verdict=FOOD_FIRST,
            reason=f"{name} is a food-first option for the measured pattern. It is not a pill substitute.",
            identity_refs=identity_refs,
            evidence_refs=tuple(sorted(matched)),
        )
    clarification = None
    if flags.get("liver_caution") and not liver and "hepatic" not in active:
        clarification = "Liver enzymes were not abnormal on this panel. Confirm they were actually measured."
    return _verdict(
        raw=raw, code=code, name=name, verdict=DISCUSS,
        reason=f"{name} has kernel evidence for {', '.join(sorted(matched))}. Discuss it. This is not a directive.",
        identity_refs=identity_refs,
        evidence_refs=tuple(sorted(matched)),
        next_clarification=clarification,
    )


def evaluate_stack(
    *,
    labs: list[dict],
    stack: list[str],
    medications: list[str] | None = None,
    conditions: list[str] | None = None,
) -> dict:
    rows = [
        verdict_for_item(item, labs=labs, medications=medications, conditions=conditions)
        for item in stack
    ]
    return {"verdicts": [row.as_dict() for row in rows]}
