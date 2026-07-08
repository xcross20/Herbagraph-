"""Aggregate safety warnings into intervention-level ratings."""

from __future__ import annotations

from app.models.enums import SafetyRiskLevel

_SEVERITY_ORDER = [
    SafetyRiskLevel.LOW,
    SafetyRiskLevel.MODERATE,
    SafetyRiskLevel.HIGH,
    SafetyRiskLevel.CONTRAINDICATED,
]

_RANK_PENALTY = {
    SafetyRiskLevel.LOW: 0.0,
    SafetyRiskLevel.MODERATE: 0.15,
    SafetyRiskLevel.HIGH: 0.35,
    SafetyRiskLevel.CONTRAINDICATED: 0.55,
}


def worst_severity(severities: list[SafetyRiskLevel]) -> SafetyRiskLevel:
    if not severities:
        return SafetyRiskLevel.LOW
    return max(severities, key=lambda s: _SEVERITY_ORDER.index(s))


def safety_rank_penalty(risk: SafetyRiskLevel) -> float:
    return _RANK_PENALTY.get(risk, 0.0)


def adjusted_confidence(base_confidence: float, risk: SafetyRiskLevel) -> float:
    """Lower rank position for higher safety concern without hiding the intervention."""
    penalty = safety_rank_penalty(risk)
    return round(max(base_confidence * (1.0 - penalty), 0.01), 4)