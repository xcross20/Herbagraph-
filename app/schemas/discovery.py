from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import DiscoveryCaseStatus, DiscoveryOutcomeStatus, DiscoveryTurnRole, LabResultStatus


class LabIngest(BaseModel):
    biomarker_name: str
    value: float
    status: LabResultStatus
    unit: str | None = None


class DiscoveryCaseCreate(BaseModel):
    presenting_concern: str = Field(min_length=1, max_length=4000)
    patient_id: uuid.UUID | None = None


class DiscoveryCaseRebuild(BaseModel):
    presenting_concern: str | None = Field(default=None, max_length=4000)
    lab_report_id: uuid.UUID | None = None
    labs: list[LabIngest] = []


class DiscoveryAnswerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=160)
    answer: Literal["yes", "no", "unknown"]
    note: str | None = Field(default=None, max_length=2000)


class DiscoveryTurnCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class DiscoveryFindingRead(BaseModel):
    kind: str
    name: str
    value: str | None = None
    status: str | None = None
    source: str


class DiscoveryInvestigationRead(BaseModel):
    label: str
    group: str
    already_assessed: bool


class DiscoveryHypothesisRead(BaseModel):
    code: str
    label: str
    branch: str
    status: str
    investigation_relevance: float
    diagnostic_certainty: float
    investigation_coverage: float
    investigation_relevance_percent: int
    diagnostic_certainty_percent: int
    investigation_coverage_percent: int
    why_limited: list[str] = []
    missing_markers: list[str] = []
    investigations: list[DiscoveryInvestigationRead] = []
    not_a_diagnosis: str = ""


class BranchCoverageRead(BaseModel):
    branch: str
    label: str
    coverage: float
    coverage_percent: int
    assessed: int
    expected: int


class MonitorItemRead(BaseModel):
    label: str
    group: str
    hypothesis_code: str
    reason: str


class DiscoveryQuestionRead(BaseModel):
    code: str
    prompt: str
    kind: str
    closes: str
    hypothesis_code: str
    utility: float


class DiscoveryOutcomeRead(BaseModel):
    id: uuid.UUID
    hypothesis_code: str
    label: str
    status: DiscoveryOutcomeStatus
    result: str | None = None
    question_code: str | None = None


class DiscoveryTurnRead(BaseModel):
    id: uuid.UUID
    role: DiscoveryTurnRole
    text: str
    kind: str
    question_code: str | None = None
    created_at: datetime


class DiscoveryCaseRead(BaseModel):
    id: uuid.UUID
    presenting_concern: str
    status: DiscoveryCaseStatus
    patient_id: uuid.UUID | None
    lab_report_id: uuid.UUID | None
    investigation_coverage: float
    investigation_coverage_percent: int
    findings: list[DiscoveryFindingRead]
    hypotheses: list[DiscoveryHypothesisRead]
    branch_coverage: list[BranchCoverageRead]
    monitor_plan: list[MonitorItemRead] = []
    next_questions: list[DiscoveryQuestionRead] = []
    current_question: DiscoveryQuestionRead | None = None
    what_changed: list[str] = []
    outcomes: list[DiscoveryOutcomeRead] = []
    turns: list[DiscoveryTurnRead] = []
    disclaimer: str
    created_at: datetime
    updated_at: datetime
