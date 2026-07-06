import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import LabReportStatus, LabResultStatus
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class LabReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lab_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LabReportStatus] = mapped_column(
        Enum(LabReportStatus, native_enum=False, length=20),
        default=LabReportStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="lab_reports")
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
