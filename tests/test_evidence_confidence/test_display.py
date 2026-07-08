"""Evidence display labels and synthesis copy."""

import pytest

from app.evidence_confidence.display import (
    evidence_display_label,
    evidence_synthesis_statement,
    intervention_classes,
)
from app.models.enums import EvidenceQualityGrade, EvidenceTier

pytestmark = pytest.mark.unit


def test_high_human_evidence_label():
    assert "🟢" in evidence_display_label(EvidenceQualityGrade.HIGH, EvidenceTier.ESTABLISHED)


def test_emerging_evidence_label():
    assert "🟠" in evidence_display_label(EvidenceQualityGrade.MODERATE, EvidenceTier.EMERGING)


def test_iron_intervention_classes():
    classes = intervention_classes("Iron", "supplement")
    assert "Iron supplementation" in classes
    assert "Evaluation for underlying causes" in classes[2]


def test_synthesis_statement_is_evidence_first():
    text = evidence_synthesis_statement("Iron", ["Iron"], "🟢 High Human Evidence")
    assert "evidence supports" in text.lower()
    assert "not a treatment directive" in text.lower()