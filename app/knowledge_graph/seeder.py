"""Reusable knowledge-graph seeding logic shared by scripts/seed_db.py and the test suite."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.food_seed_data import (
    FOOD_COMPOUND_EVIDENCE_CLAIMS,
    FOOD_COMPOUND_SOURCES,
    FOOD_INTERVENTIONS,
    PHYTOCHEMICAL_COMPOUNDS,
)
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS
from app.knowledge_graph.seed_data import BIOMARKERS, EVIDENCE_CLAIMS, INTERVENTIONS, PATHWAYS
from app.models.biomarker import Biomarker
from app.models.compound import Compound, InterventionCompound
from app.models.evidence import EvidenceClaim
from app.models.food_compound_source import FoodCompoundSource
from app.models.intervention import Intervention
from app.models.pathway import Pathway
from app.models.safety import DrugInteraction, SafetyFlag


def _build_intervention(data: dict, compound_by_name: dict[str, Compound]) -> Intervention:
    description = data.get("description")
    if methodology := data.get("methodology_spec"):
        protocol_line = f"Validated protocol: {methodology}"
        description = f"{description}\n\n{protocol_line}" if description else protocol_line

    intervention = Intervention(
        name=data["name"],
        category=data["category"],
        description=description,
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
    for compound_data in data.get("compounds", []):
        compound = compound_by_name.get(compound_data["name"])
        if compound is None:
            raw_cid = compound_data.get("pubchem_cid")
            compound = Compound(
                name=compound_data["name"],
                primary_target=compound_data.get("primary_target"),
                pubchem_cid=int(raw_cid) if raw_cid is not None else None,
            )
            compound_by_name[compound_data["name"]] = compound
        intervention.compounds.append(InterventionCompound(compound=compound, role=compound_data.get("role")))
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
        db.add(
            Pathway(
                code=pathway["code"],
                name=pathway["name"],
                description=pathway.get("description"),
                pathway_type=pathway.get("pathway_type", "signaling"),
            )
        )

    intervention_by_name: dict[str, Intervention] = {}
    compound_by_name: dict[str, Compound] = {}
    for data in [*PHYTOCHEMICAL_COMPOUNDS, *INTERVENTIONS, *FOOD_INTERVENTIONS, *PEPTIDE_INTERVENTIONS]:
        if data["name"] in intervention_by_name:
            continue
        intervention = _build_intervention(data, compound_by_name)
        db.add(intervention)
        intervention_by_name[data["name"]] = intervention

    await db.flush()

    for claim in [*EVIDENCE_CLAIMS, *FOOD_COMPOUND_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS]:
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
                recommendation_intent=claim.get("recommendation_intent"),
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
        "interventions": len(intervention_by_name),  # deduplicated across supplement/phytochemical overlap
        "evidence_claims": len(EVIDENCE_CLAIMS) + len(FOOD_COMPOUND_EVIDENCE_CLAIMS) + len(PEPTIDE_EVIDENCE_CLAIMS),
        "food_compound_sources": len(FOOD_COMPOUND_SOURCES),
    }
