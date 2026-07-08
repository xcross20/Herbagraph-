import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AnalysisSessionStatus, AnalysisType, LabReportStatus


class DashboardPatientSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    latest_report_id: uuid.UUID | None = None
    latest_report_confidence: float | None = None
    lab_report_count: int = 0
    analysis_session_count: int = 0


class DashboardReportSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    patient_display_name: str | None = None
    title: str
    overall_confidence: float
    created_at: datetime
    analysis_session_id: uuid.UUID | None = None


class DashboardLabSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    original_filename: str
    status: LabReportStatus
    latest_report_id: uuid.UUID | None = None
    created_at: datetime


class DashboardSessionSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    title: str
    status: AnalysisSessionStatus
    analysis_type: AnalysisType
    latest_report_id: uuid.UUID | None = None
    report_confidence: float | None = None
    created_at: datetime


class WorkspaceDashboardRead(BaseModel):
    user_email: str
    user_full_name: str | None = None
    patients: list[DashboardPatientSummary]
    recent_reports: list[DashboardReportSummary]
    recent_labs: list[DashboardLabSummary]
    recent_sessions: list[DashboardSessionSummary]


class PatientOverviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    date_of_birth: str | None = None
    age: int | None = None
    biological_sex: str | None = None
    notes: str | None = None
    created_at: datetime
    latest_report_id: uuid.UUID | None = None
    latest_report_confidence: float | None = None
    top_priorities: list[str] = []
    recent_abnormal_biomarkers: list[dict] = []
    lab_reports: list[DashboardLabSummary] = []
    analysis_sessions: list[DashboardSessionSummary] = []
    context_summary: dict[str, list[str]] = {}