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
    idempotency_key: str | None = Field(default=None, max_length=80)


class DiscoveryDisclaimerAck(BaseModel):
    version: str = Field(default="discovery_disclaimer_v1", max_length=80)


class DiscoveryTestPlanItemRead(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    patient_id: uuid.UUID | None
    label: str
    reason: str | None
    status: str
    source: str
    created_at: datetime


class DiscoveryTestPlanCreate(BaseModel):
    labels: list[str] = []


class DiscoveryDocumentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    text: str = Field(min_length=1, max_length=20000)


class LongitudinalSnapshotRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    version: int
    is_current: bool
    payload: dict
    created_at: datetime
    updated_at: datetime


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
    investigation_coverage: float
    investigation_relevance_percent: int
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
    options: list[str] = []


class DiscoveryInteractionRead(BaseModel):
    type: str
    options: list[str] = []
    accepted_types: list[str] = []


class DiscoveryActionRead(BaseModel):
    type: str
    objective: str
    question_id: str | None = None
    prompt: str | None = None


class DiscoveryTurnStateRead(BaseModel):
    stage: str
    safety_status: str
    intents: list[str] = []
    selected_action: DiscoveryActionRead
    problem_representation: str = ""
    unknowns: list[str] = []
    contradictions: list[str] = []
    what_changed: list[str] = []
    critic: str = ""
    safety_evidence_status: str | None = None
    safety_confidence: str | None = None
    safety_override: bool = False
    discovery_can_continue: bool = True
    clinical_followup_needed: bool = False
    safety_net: dict | None = None


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
    stage: str = "opening"
    problem_representation: str | None = None
    interaction: DiscoveryInteractionRead | None = None
    turn_state: DiscoveryTurnStateRead | None = None
    investigation_map: dict | None = None
    map_version: int | None = None
    confidence_increasers: list[dict] = []
    timeline: list[dict] = []
    prior_workup: list[dict] = []
    memory_items: list[dict] = []
    literature: list[dict] = []
    safety: dict | None = None
    last_visit: dict | None = None
    disclaimer: str
    created_at: datetime
    updated_at: datetime


class DiscoveryDocumentRead(BaseModel):
    kind: str
    accepted: bool
    detail: str
    case: DiscoveryCaseRead | None = None


class DiscoveryMonitoringCreate(BaseModel):
    target: str
    observation_time: str
    outcome_kind: str
    source_event_id: str
    exposure: str | None = None
    adherence: str | None = None
    notes: str | None = None


class DiscoveryMonitoringRead(BaseModel):
    id: uuid.UUID
    target: str
    observation_time: str
    outcome_kind: str
    exposure: str | None = None
    adherence: str | None = None
    notes: str | None = None
    causal_claim: bool
