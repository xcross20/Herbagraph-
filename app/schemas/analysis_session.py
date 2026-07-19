import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnalysisSessionStatus, AnalysisType, KnowledgePath, LabReportStatus


class AnalysisSessionCreate(BaseModel):
    title: str = "Integrated Lab Analysis"
    patient_id: uuid.UUID | None = None
    analysis_type: AnalysisType = AnalysisType.MULTI_REPORT_SNAPSHOT


class AnalysisSessionRunRequest(BaseModel):
    """Optional body for POST /analysis-sessions/{id}/run."""

    knowledge_path: KnowledgePath = KnowledgePath.LEGACY


class AnalysisSessionLabLinkRead(BaseModel):
    lab_report_id: uuid.UUID
    panel_label: str | None = None
    original_filename: str | None = None
    status: LabReportStatus | None = None


class AnalysisSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    title: str
    analysis_type: AnalysisType
    status: AnalysisSessionStatus
    report_confidence: float | None = None
    analysis_date: datetime | None = None
    error_message: str | None = None
    latest_report_id: uuid.UUID | None = None
    anchor_lab_report_id: uuid.UUID | None = None
    created_at: datetime
    lab_reports: list[AnalysisSessionLabLinkRead] = []


class AnalysisSessionRunResponse(BaseModel):
    analysis_session_id: uuid.UUID
    task_id: str
    status: AnalysisSessionStatus
    knowledge_path: KnowledgePath | str = KnowledgePath.LEGACY
    message: str


class IntegratedUploadResponse(BaseModel):
    analysis_session_id: uuid.UUID
    uploaded: list[dict]
    message: str


class AnalysisSessionLinkLabsRequest(BaseModel):
    lab_report_ids: list[uuid.UUID] = Field(min_length=1)