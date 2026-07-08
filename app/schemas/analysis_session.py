import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnalysisSessionStatus, LabReportStatus


class AnalysisSessionCreate(BaseModel):
    title: str = "Integrated Lab Analysis"
    patient_id: uuid.UUID | None = None


class AnalysisSessionLabLinkRead(BaseModel):
    lab_report_id: uuid.UUID
    panel_label: str | None = None
    original_filename: str | None = None
    status: LabReportStatus | None = None


class AnalysisSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: AnalysisSessionStatus
    analysis_date: datetime | None = None
    error_message: str | None = None
    latest_report_id: uuid.UUID | None = None
    created_at: datetime
    lab_reports: list[AnalysisSessionLabLinkRead] = []


class AnalysisSessionRunResponse(BaseModel):
    analysis_session_id: uuid.UUID
    task_id: str
    status: AnalysisSessionStatus
    message: str


class IntegratedUploadResponse(BaseModel):
    analysis_session_id: uuid.UUID
    uploaded: list[dict]
    message: str