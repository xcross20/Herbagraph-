"""Reusable knowledge-graph seeding logic shared by scripts/seed_db.py and the test suite."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.food_seed_data import (
    FOOD_COMPOUND_EVIDENCE_CLAIMS,
    FOOD_COMPOUND_SOURCES,
    FOOD_INTERVENTIONS,
    PHYTOCHEMICAL_COMPOUNDS,
)
from app.knowledge_graph.seed_data import BIOMARKERS, EVIDENCE_CLAIMS, INTERVENTIONS, PATHWAYS
from app.models.biomarker import Biomarker
from app.models.evidence import EvidenceClaim
from app.models.food_compound_source import FoodCompoundSource
from app.models.intervention import Intervention
from app.models.pathway import Pathway
from app.models.safety import DrugInteraction, SafetyFlag


def _build_intervention(data: dict) -> Intervention:
    intervention = Intervention(
        name=data["name"],
        category=data["category"],
        description=data.get("description"),
        mechanism=data.get("mechanism"),
        is_regulated=data.get("is_regulated", False),
        regulation_note=data.get("regulation_note"),
    )
    for flag in data.get("safety_flags", []):
        intervention.safety_flags.append(
            SafetyFlag(condition=flag["condition"], severity=flag["severity"], note=flag.get("note"))
        )
    for interaction in data.get("drug_interactions", []):
        intervention.drug_interactions.append(
            DrugInteraction(
                drug_name=interaction["drug_name"],
                severity=interaction["severity"],
                mechanism=interaction.get("mechanism"),
                note=interaction.get("note"),
            )
        )
    return intervention


async def is_seeded(db: AsyncSession) -> bool:
    count = (await db.execute(select(func.count()).select_from(Biomarker))).scalar()
    return bool(count)


async def seed_knowledge_graph(db: AsyncSession) -> dict[str, int]:
    """Insert the full HerbaGraph knowledge graph into the given session and commit.

    Returns a dict of counts for caller logging/assertions. Not idempotent by itself --
    callers should check `is_seeded` first if they want to skip re-seeding.
    """
    for biomarker in BIOMARKERS:
        db.add(Biomarker(**biomarker))
    for pathway in PATHWAYS:
        db.add(Pathway(**pathway))

    intervention_by_name: dict[str, Intervention] = {}
    for data in [*INTERVENTIONS, *PHYTOCHEMICAL_COMPOUNDS, *FOOD_INTERVENTIONS]:
        intervention = _build_intervention(data)
        db.add(intervention)
        intervention_by_name[data["name"]] = intervention

    await db.flush()

    for claim in [*EVIDENCE_CLAIMS, *FOOD_COMPOUND_EVIDENCE_CLAIMS]:
        intervention = intervention_by_name[claim["intervention_name"]]
        db.add(
            EvidenceClaim(
                intervention_id=intervention.id,
                biomarker_name=claim.get("biomarker_name"),
                pathway_code=claim.get("pathway_code"),
                effect=claim["effect"],
                evidence_level=claim["evidence_level"],
                pmid=claim.get("pmid"),
                summary=claim.get("summary"),
            )
        )

    for food_name, compound_name, richness, serving, note in FOOD_COMPOUND_SOURCES:
        db.add(
            FoodCompoundSource(
                food_intervention_id=intervention_by_name[food_name].id,
                compound_intervention_id=intervention_by_name[compound_name].id,
                richness=richness,
                typical_serving=serving,
                note=note,
            )
        )

    await db.commit()
    return {
        "biomarkers": len(BIOMARKERS),
        "pathways": len(PATHWAYS),
        "interventions": len(intervention_by_name),
        "evidence_claims": len(EVIDENCE_CLAIMS) + len(FOOD_COMPOUND_EVIDENCE_CLAIMS),
        "food_compound_sources": len(FOOD_COMPOUND_SOURCES),
    }
