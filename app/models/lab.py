import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import LabProcessingStage, LabReportStatus, LabResultStatus, ReportGenerationStage
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class LabReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lab_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    # Optional: only set in clinic mode, when a clinician User uploads on behalf of one
    # of their Patients. Individual self-service users leave this null -- their reports
    # belong directly to their own User row exactly as before this field was added.
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LabReportStatus] = mapped_column(
        Enum(LabReportStatus, native_enum=False, length=20),
        default=LabReportStatus.PENDING,
        nullable=False,
    )
    processing_stage: Mapped[LabProcessingStage | None] = mapped_column(
        Enum(LabProcessingStage, native_enum=False, length=20),
        nullable=True,
    )
    report_stage: Mapped[ReportGenerationStage | None] = mapped_column(
        Enum(ReportGenerationStage, native_enum=False, length=30),
        nullable=True,
    )
    report_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_report_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="lab_reports")
    patient: Mapped["Patient | None"] = relationship(back_populates="lab_reports")
    lab_results: Mapped[list["LabResult"]] = relationship(
        back_populates="lab_report", cascade="all, delete-orphan"
    )
    reports: Mapped[list["RecommendationReport"]] = relationship(
        back_populates="lab_report", cascade="all, delete-orphan"
    )


class LabResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lab_results"

    lab_report_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("lab_reports.id"), nullable=False)
    biomarker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_test_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_range_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_range_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[LabResultStatus] = mapped_column(
        Enum(LabResultStatus, native_enum=False, length=20), nullable=False
    )

    lab_report: Mapped["LabReport"] = relationship(back_populates="lab_results")
