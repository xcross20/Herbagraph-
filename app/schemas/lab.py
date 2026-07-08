import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import LabProcessingStage, LabReportStatus, LabResultStatus, ReportGenerationStage


class LabResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    biomarker_name: str
    value: float
    unit: str | None = None
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    status: LabResultStatus


class LabUploadResponse(BaseModel):
    lab_report_id: uuid.UUID
    task_id: str
    message: str
    status: LabReportStatus


class LabReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    status: LabReportStatus
    processing_stage: LabProcessingStage | None = None
    report_stage: ReportGenerationStage | None = None
    report_error_message: str | None = None
    latest_report_id: uuid.UUID | None = None
    error_message: str | None = None
    created_at: datetime
    lab_results: list[LabResultRead] = []


class LabReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID | None = None
    original_filename: str
    status: LabReportStatus
    report_stage: ReportGenerationStage | None = None
    latest_report_id: uuid.UUID | None = None
    error_message: str | None = None
    created_at: datetime
