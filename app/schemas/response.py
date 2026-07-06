import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResponseTrackingCreate(BaseModel):
    intervention_name: str
    baseline_lab_report_id: uuid.UUID
    patient_id: uuid.UUID | None = None
    started_at: datetime | None = None


class ResponseTrackingFollowUp(BaseModel):
    follow_up_lab_report_id: uuid.UUID


class ResponseTrackingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    intervention_name: str
    baseline_lab_report_id: uuid.UUID
    follow_up_lab_report_id: uuid.UUID | None = None
    started_at: datetime | None = None
    created_at: datetime


class BiomarkerChangeRead(BaseModel):
    biomarker_name: str
    baseline_value: float
    follow_up_value: float
    unit: str | None = None
    percent_change: float | None = None
    direction: str
    direction_label: str


class SystemResponseRead(BaseModel):
    system_code: str
    system_name: str
    response: str
    response_label: str
    confidence: str
    contributing_biomarkers: list[str] = []


class EvidenceContextRead(BaseModel):
    intervention_name: str
    summary: str | None = None
    evidence_level: str
    pmid: str | None = None


class BiologicalResponseReportRead(BaseModel):
    intervention_name: str
    baseline_date: datetime | None = None
    follow_up_date: datetime | None = None
    duration_days: int | None = None
    biomarker_changes: list[BiomarkerChangeRead]
    system_responses: list[SystemResponseRead]
    evidence_context: list[EvidenceContextRead]
    disclaimer: str
