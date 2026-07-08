import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReasoningAgreement = Literal["completely", "mostly", "partially", "no"]
TimeSavedBucket = Literal["under_5", "5_10", "10_20", "over_20"]
PatientEncounterComfort = Literal["yes", "yes_minor_edits", "background_only", "no"]
WouldUseAgain = Literal["yes", "probably", "unsure", "no"]


class ReportFeedbackCreate(BaseModel):
    clinical_usefulness_score: int = Field(ge=1, le=5)
    reasoning_agreement: ReasoningAgreement
    estimated_time_saved_bucket: TimeSavedBucket | None = None
    patient_encounter_comfort: PatientEncounterComfort
    free_text_feedback: str | None = None
    safety_concerns: str | None = None
    most_useful_section: str | None = None
    least_useful_section: str | None = None
    would_use_again: WouldUseAgain | None = None


class ReportFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    clinical_usefulness_score: int
    reasoning_agreement: str
    trust_score: int | None = None
    estimated_time_saved_minutes: int | None = None
    patient_encounter_comfort: str | None = None
    would_use_again: str | None = None
    most_useful_section: str | None = None
    least_useful_section: str | None = None
    safety_concerns: str | None = None
    free_text_feedback: str | None = None
    created_at: datetime


class ValidationEventCreate(BaseModel):
    report_id: uuid.UUID | None = None
    event_type: str = Field(min_length=1, max_length=50)
    section_name: str | None = Field(default=None, max_length=80)
    metadata: dict | None = None


class ValidationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID | None
    event_type: str
    section_name: str | None = None
    created_at: datetime


class ValidationDashboardRead(BaseModel):
    reports_generated: int
    reports_reviewed: int
    average_usefulness_score: float | None
    average_trust_score: float | None
    average_time_saved_minutes: float | None
    would_use_again_percent: float | None
    most_useful_section: str | None
    most_useful_section_percent: float | None
    least_useful_section: str | None
    least_useful_section_percent: float | None
    most_opened_section: str | None
    report_confidence_distribution: dict[str, float]
    most_requested_biomarkers: list[dict]
    disputed_recommendations: list[dict]
    free_text_feedback: list[dict]
    recent_events: list[ValidationEventRead]