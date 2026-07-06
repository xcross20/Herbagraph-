import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.knowledge_graph.food_seed_data import COMPOUND_TO_FOOD_SOURCES, FOOD_TO_COMPOUNDS
from app.models.biomarker import Biomarker
from app.models.enums import InterventionCategory
from app.models.intervention import Intervention
from app.models.pathway import Pathway
from app.models.user import User
from app.schemas.evidence import (
    BiomarkerRead,
    CompoundFoodSourcesResponse,
    FoodCompoundsResponse,
    InterventionDetail,
    InterventionSummary,
    PathwayRead,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/interventions", response_model=list[InterventionSummary])
async def list_interventions(
    category: InterventionCategory | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Intervention]:
    query = select(Intervention)
    if category is not None:
        query = query.where(Intervention.category == category)
    if search:
        query = query.where(Intervention.name.ilike(f"%{search}%"))
    query = query.order_by(Intervention.name).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/interventions/{intervention_id}", response_model=InterventionDetail)
async def get_intervention(
    intervention_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Intervention:
    result = await db.execute(select(Intervention).where(Intervention.id == intervention_id))
    intervention = result.scalar_one_or_none()
    if intervention is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found")
    await db.refresh(intervention, attribute_names=["safety_flags", "drug_interactions"])
    return intervention


@router.get("/biomarkers", response_model=list[BiomarkerRead])
async def list_biomarkers(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Biomarker]:
    result = await db.execute(select(Biomarker).order_by(Biomarker.canonical_name))
    return list(result.scalars().all())


@router.get("/pathways", response_model=list[PathwayRead])
async def list_pathways(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Pathway]:
    result = await db.execute(select(Pathway).order_by(Pathway.code))
    return list(result.scalars().all())


@router.get("/compounds/{compound_name}/food-sources", response_model=CompoundFoodSourcesResponse)
async def get_compound_food_sources(
    compound_name: str, current_user: User = Depends(get_current_user)
) -> CompoundFoodSourcesResponse:
    sources = COMPOUND_TO_FOOD_SOURCES.get(compound_name)
    if sources is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown compound '{compound_name}'")
    return CompoundFoodSourcesResponse(compound=compound_name, food_sources=sources)


@router.get("/foods/{food_name}/compounds", response_model=FoodCompoundsResponse)
async def get_food_compounds(
    food_name: str, current_user: User = Depends(get_current_user)
) -> FoodCompoundsResponse:
    compounds = FOOD_TO_COMPOUNDS.get(food_name)
    if compounds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown food '{food_name}'")
    return FoodCompoundsResponse(food=food_name, compounds=compounds)
