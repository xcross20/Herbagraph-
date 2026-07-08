import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AnalysisSessionStatus, AnalysisType
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Integrated Lab Analysis")
    analysis_type: Mapped[AnalysisType] = mapped_column(
        Enum(AnalysisType, native_enum=False, length=40),
        default=AnalysisType.MULTI_REPORT_SNAPSHOT,
        nullable=False,
    )
    report_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AnalysisSessionStatus] = mapped_column(
        Enum(AnalysisSessionStatus, native_enum=False, length=30),
        default=AnalysisSessionStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_report_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    lab_links: Mapped[list["AnalysisSessionLabReport"]] = relationship(
        back_populates="analysis_session", cascade="all, delete-orphan"
    )
    integrated_results: Mapped[list["IntegratedBiomarkerResult"]] = relationship(
        back_populates="analysis_session", cascade="all, delete-orphan"
    )


class AnalysisSessionLabReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_session_lab_reports"

    analysis_session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("analysis_sessions.id"), nullable=False, index=True
    )
    lab_report_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("lab_reports.id"), nullable=False, index=True)
    panel_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    analysis_session: Mapped["AnalysisSession"] = relationship(back_populates="lab_links")
    lab_report: Mapped["LabReport"] = relationship()


class IntegratedBiomarkerResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "integrated_biomarker_results"

    analysis_session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("analysis_sessions.id"), nullable=False, index=True
    )
    biomarker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_lab_report_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("lab_reports.id"), nullable=False)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    merge_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    analysis_session: Mapped["AnalysisSession"] = relationship(back_populates="integrated_results")