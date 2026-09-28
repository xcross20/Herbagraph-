"""Typed evidence claim. A card is allowed only when every field is present
and the layer is allowed to author one.

Growth literature can still be stored. It cannot set can_author_card.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.knowledge_graph.claim_layers import (
    CARD_ELIGIBLE_LAYERS,
    LAYER_GROWTH,
    LAYER_KERNEL,
    layer_of,
)

# Marker names are the normalized lab names the pipeline already emits.
INDICATION_FAMILY_MARKERS: dict[str, frozenset[str]] = {
    "lipid": frozenset({"LDL", "HDL", "Triglycerides", "Total Cholesterol", "Non-HDL Cholesterol"}),
    "glycemic": frozenset({"Glucose", "HbA1c", "Insulin", "HOMA-IR"}),
    "hepatic": frozenset({"ALT", "AST", "GGT"}),
}


class IndicationFamily(str, Enum):
    LIPID = "lipid"
    GLYCEMIC = "glycemic"
    HEPATIC = "hepatic"
    OTHER = "other"


class RecommendationAuthority(str, Enum):
    KERNEL = "kernel"
    CURATED_LONGTAIL = "curated_longtail"
    GROWTH_CONTEXT = "growth_context"


class EvidenceLayer(str, Enum):
    KERNEL = "kernel"
    CURATED_LONGTAIL = "curated_longtail"
    GROWTH = "growth"


_CARD_INTENTS = frozenset({"primary", "nutritional_repletion", "collateral"})


@dataclass(frozen=True)
class InterventionIdentity:
    """Exact form. Goldenseal is not berberine; cassia is not Ceylon."""

    name: str
    preparation: str | None = None


@dataclass(frozen=True)
class MeasurementTarget:
    biomarker_name: str
    family: IndicationFamily


@dataclass(frozen=True)
class ApplicabilityScope:
    population: str
    context: str | None = None


@dataclass(frozen=True)
class EvidenceClaim:
    intervention: InterventionIdentity
    measurement: MeasurementTarget
    scope: ApplicabilityScope
    authority: RecommendationAuthority
    layer: EvidenceLayer
    recommendation_intent: str
    pmid: str | None = None

    @property
    def can_author_card(self) -> bool:
        if self.layer == EvidenceLayer.GROWTH or self.authority == RecommendationAuthority.GROWTH_CONTEXT:
            return False
        if self.layer.value not in CARD_ELIGIBLE_LAYERS:
            return False
        if self.recommendation_intent not in _CARD_INTENTS:
            return False
        if not self.intervention.name or not self.measurement.biomarker_name or not self.scope.population:
            return False
        return True


def family_for_biomarker(biomarker_name: str) -> IndicationFamily:
    for family, markers in INDICATION_FAMILY_MARKERS.items():
        if biomarker_name in markers:
            return IndicationFamily(family)
    return IndicationFamily.OTHER


def claim_from_legacy(row: dict, *, population: str) -> EvidenceClaim:
    """Adapt a catalog dict. Growth rows cannot come back as card authors."""
    layer_name = layer_of(row)
    layer = EvidenceLayer(layer_name) if layer_name in {item.value for item in EvidenceLayer} else EvidenceLayer.KERNEL
    if layer_name == LAYER_GROWTH:
        authority = RecommendationAuthority.GROWTH_CONTEXT
        intent = "context_only"
    elif layer_name == LAYER_KERNEL:
        authority = RecommendationAuthority.KERNEL
        intent = str(row.get("recommendation_intent") or "collateral")
    else:
        authority = RecommendationAuthority.CURATED_LONGTAIL
        intent = str(row.get("recommendation_intent") or "collateral")
    biomarker = str(row.get("biomarker_name") or "")
    return EvidenceClaim(
        intervention=InterventionIdentity(
            name=str(row.get("intervention_name") or ""),
            preparation=row.get("preparation"),
        ),
        measurement=MeasurementTarget(biomarker_name=biomarker, family=family_for_biomarker(biomarker)),
        scope=ApplicabilityScope(population=population, context=row.get("context")),
        authority=authority,
        layer=layer,
        recommendation_intent=intent,
        pmid=str(row["pmid"]) if row.get("pmid") else None,
    )
