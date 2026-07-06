import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Compound(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A chemical constituent of an Intervention (e.g. AKBA within Boswellia serrata).

    Completes the Intervention -> Compound -> Target -> Pathway -> Biomarker chain: the
    compound's `primary_target` is the molecular target/enzyme/receptor it acts on (the
    "Target" node); Pathway/Biomarker linkage comes from the parent Intervention's own
    EvidenceClaims, since the clinical evidence retrieved is almost always about the whole
    herb/food, not an isolated constituent in isolation.

    `pubchem_cid` is left unset by default -- rather than embed potentially-stale/incorrect
    identifiers in static seed data, look it up on demand via app.integrations.pubchem.
    """

    __tablename__ = "compounds"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_target: Mapped[str | None] = mapped_column(String(150), nullable=True)
    pubchem_cid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    interventions: Mapped[list["InterventionCompound"]] = relationship(
        back_populates="compound", cascade="all, delete-orphan"
    )


class InterventionCompound(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Join row: which compound(s) an intervention is constituted of."""

    __tablename__ = "intervention_compounds"

    intervention_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interventions.id"), nullable=False
    )
    compound_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("compounds.id"), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="compounds")
    compound: Mapped["Compound"] = relationship(back_populates="interventions")
