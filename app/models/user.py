import uuid

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20), default=UserRole.INDIVIDUAL, nullable=False
    )
    clinic_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    health_profile: Mapped["HealthProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    lab_reports: Mapped[list["LabReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reports: Mapped[list["RecommendationReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    patients: Mapped[list["Patient"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class HealthProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "health_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), unique=True, nullable=False)
    age_range: Mapped[str | None] = mapped_column(String(20), nullable=True)
    biological_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    health_goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    current_medications: Mapped[list[str]] = mapped_column(JSON, default=list)
    current_supplements: Mapped[list[str]] = mapped_column(JSON, default=list)
    known_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    custom_biomarkers: Mapped[list[dict]] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="health_profile")
