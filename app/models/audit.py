import uuid

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable audit trail for clinician traceability and security review."""

    __tablename__ = "audit_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)