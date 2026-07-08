"""Safety profile models — no pipeline imports (avoids circular dependencies)."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import SafetyRiskLevel, SafetyWarningEvidenceLevel


class SafetyWarningDetail(BaseModel):
    warning_type: str
    relationship: str
    severity: SafetyRiskLevel
    mechanism: str
    evidence_level: SafetyWarningEvidenceLevel | None = None
    citations: list[str] = []
    source_entity: str
    target_entity: str
    note: str | None = None


class InterventionSafetyProfile(BaseModel):
    safety_rating: SafetyRiskLevel = SafetyRiskLevel.LOW
    warnings: list[SafetyWarningDetail] = []
    contraindications: list[str] = []
    organ_cautions: list[str] = []
    pregnancy_lactation_warnings: list[str] = []
    requires_prominent_warning: bool = False
    is_regulated: bool = False
    regulation_note: str | None = None