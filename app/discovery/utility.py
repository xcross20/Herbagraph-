"""Test utility: information value, not a hunt to 90% confidence.

utility = (information_gain × actionability × safety × coverage_gain)
          / (cost + burden + risk + redundancy)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UtilityInputs:
    information_gain: float
    actionability: float
    safety: float
    coverage_gain: float
    cost: float = 0.30
    burden: float = 0.20
    risk: float = 0.10
    redundancy: float = 0.0


# Named checks used by Guided Discovery. Values are relative, not prices.
_PROFILES: dict[str, UtilityInputs] = {
    "MMA": UtilityInputs(0.92, 0.88, 0.96, 0.80, cost=0.22, burden=0.12, risk=0.04),
    "Homocysteine": UtilityInputs(0.84, 0.80, 0.96, 0.70, cost=0.22, burden=0.12, risk=0.04),
    "HbA1c": UtilityInputs(0.86, 0.90, 0.97, 0.75, cost=0.20, burden=0.12, risk=0.03),
    "Insulin": UtilityInputs(0.78, 0.74, 0.96, 0.65, cost=0.22, burden=0.14, risk=0.04),
    "TSH": UtilityInputs(0.80, 0.82, 0.97, 0.70, cost=0.18, burden=0.10, risk=0.03),
    "Free T4": UtilityInputs(0.76, 0.78, 0.97, 0.62, cost=0.20, burden=0.10, risk=0.03),
    "EMG/NCS status": UtilityInputs(0.70, 0.62, 0.78, 0.55, cost=0.62, burden=0.55, risk=0.18),
    "Skin biopsy if exam and labs remain unexplained": UtilityInputs(
        0.72, 0.58, 0.62, 0.50, cost=0.70, burden=0.68, risk=0.28
    ),
    "Medication history (metformin, PPI)": UtilityInputs(
        0.74, 0.86, 0.99, 0.45, cost=0.04, burden=0.06, risk=0.01
    ),
    "Focused neurologic / sensory exam": UtilityInputs(
        0.80, 0.84, 0.99, 0.60, cost=0.12, burden=0.18, risk=0.02
    ),
}

_DEFAULT = UtilityInputs(0.55, 0.50, 0.85, 0.40, cost=0.35, burden=0.30, risk=0.12)


def test_utility(inputs: UtilityInputs) -> float:
    numerator = (
        inputs.information_gain
        * inputs.actionability
        * inputs.safety
        * (0.5 + 0.5 * inputs.coverage_gain)
    )
    denominator = max(0.05, inputs.cost + inputs.burden + inputs.risk + inputs.redundancy)
    return round(min(1.0, numerator / denominator), 4)


def utility_for_marker(label: str) -> float:
    return test_utility(_PROFILES.get(label, _DEFAULT))
