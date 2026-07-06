import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import InterventionCategory, Richness


class FoodSourceRead(BaseModel):
    food: str
    richness: Richness
    typical_serving: str | None = None
    note: str | None = None


class SafetyFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition: str
    severity: str
    note: str | None = None


class DrugInteractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    drug_name: str
    severity: str
    mechanism: str | None = None
    note: str | None = None


class InterventionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: InterventionCategory
    description: str | None = None


class InterventionDetail(InterventionSummary):
    mechanism: str | None = None
    is_regulated: bool
    regulation_note: str | None = None
    safety_flags: list[SafetyFlagRead] = []
    drug_interactions: list[DrugInteractionRead] = []


class BiomarkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_name: str
    category: str
    description: str | None = None
    default_unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None


class PathwayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None


class CompoundFoodSourcesResponse(BaseModel):
    compound: str
    food_sources: list[FoodSourceRead]


class FoodCompoundInfo(BaseModel):
    compound: str
    richness: Richness
    typical_serving: str | None = None
    note: str | None = None


class FoodCompoundsResponse(BaseModel):
    food: str
    compounds: list[FoodCompoundInfo]
