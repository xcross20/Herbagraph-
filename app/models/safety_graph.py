"""Safety Engine graph persistence — nodes and typed relationships."""

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    SafetyNodeType,
    SafetyRelationshipType,
    SafetyRiskLevel,
    SafetyWarningEvidenceLevel,
)
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class SafetyGraphNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "safety_graph_nodes"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    node_type: Mapped[SafetyNodeType] = mapped_column(
        Enum(SafetyNodeType, native_enum=False, length=30), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)

    outgoing_edges: Mapped[list["SafetyGraphEdge"]] = relationship(
        back_populates="source_node",
        foreign_keys="SafetyGraphEdge.source_node_id",
        cascade="all, delete-orphan",
    )


class SafetyGraphEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "safety_graph_edges"

    source_node_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("safety_graph_nodes.id"), nullable=False)
    target_node_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("safety_graph_nodes.id"), nullable=False)
    relationship_type: Mapped[SafetyRelationshipType] = mapped_column(
        Enum(SafetyRelationshipType, native_enum=False, length=30), nullable=False
    )
    severity: Mapped[SafetyRiskLevel] = mapped_column(
        Enum(SafetyRiskLevel, native_enum=False, length=20), nullable=False
    )
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_level: Mapped[SafetyWarningEvidenceLevel | None] = mapped_column(
        Enum(SafetyWarningEvidenceLevel, native_enum=False, length=30), nullable=True
    )
    citations: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_node: Mapped["SafetyGraphNode"] = relationship(
        back_populates="outgoing_edges", foreign_keys=[source_node_id]
    )
    target_node: Mapped["SafetyGraphNode"] = relationship(foreign_keys=[target_node_id])