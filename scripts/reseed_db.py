#!/usr/bin/env python
"""Force-reseed the HerbaGraph knowledge graph from expanded seed catalogs.

Truncates knowledge-graph tables and reloads from seed_data catalogs.
Does NOT delete users, lab reports, or recommendation reports.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select

from app.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.knowledge_graph.food_seed_data import (  # noqa: E402
    FOOD_COMPOUND_EVIDENCE_CLAIMS,
    FOOD_COMPOUND_SOURCES,
    FOOD_INTERVENTIONS,
    PHYTOCHEMICAL_COMPOUNDS,
)
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS  # noqa: E402
from app.knowledge_graph.seed_data import (  # noqa: E402
    BIOMARKERS,
    EVIDENCE_CLAIMS,
    INTERVENTIONS,
    PATHWAYS,
    expected_seeded_intervention_count,
)
from app.knowledge_graph.seeder import seed_knowledge_graph  # noqa: E402
from app.models.biomarker import Biomarker  # noqa: E402
from app.models.compound import Compound, InterventionCompound  # noqa: E402
from app.models.evidence import EvidenceClaim  # noqa: E402
from app.models.food_compound_source import FoodCompoundSource  # noqa: E402
from app.models.intervention import Intervention  # noqa: E402
from app.models.pathway import Pathway  # noqa: E402
from app.models.safety import DrugInteraction, SafetyFlag  # noqa: E402


async def _clear_knowledge_graph(db) -> None:
    await db.execute(delete(FoodCompoundSource))
    await db.execute(delete(EvidenceClaim))
    await db.execute(delete(InterventionCompound))
    await db.execute(delete(DrugInteraction))
    await db.execute(delete(SafetyFlag))
    await db.execute(delete(Intervention))
    await db.execute(delete(Compound))
    await db.execute(delete(Biomarker))
    await db.execute(delete(Pathway))
    await db.commit()


async def reseed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    expected_interventions = expected_seeded_intervention_count(
        food_interventions=FOOD_INTERVENTIONS,
        phytochemical_compounds=PHYTOCHEMICAL_COMPOUNDS,
        peptide_interventions=PEPTIDE_INTERVENTIONS,
    )
    expected_claims = len(EVIDENCE_CLAIMS) + len(FOOD_COMPOUND_EVIDENCE_CLAIMS) + len(PEPTIDE_EVIDENCE_CLAIMS)

    async with AsyncSessionLocal() as db:
        before = (await db.execute(select(func.count()).select_from(Intervention))).scalar()
        print(f"Clearing knowledge graph ({before} existing interventions)...")
        await _clear_knowledge_graph(db)

        counts = await seed_knowledge_graph(db)
        after = (await db.execute(select(func.count()).select_from(Intervention))).scalar()

        print(
            f"Reseeded {counts['biomarkers']} biomarkers, {counts['pathways']} pathways, "
            f"{counts['interventions']} interventions (expected {expected_interventions}), "
            f"{counts['evidence_claims']} evidence claims (expected {expected_claims}), "
            f"{counts['food_compound_sources']} food-compound sources."
        )
        assert after == expected_interventions, f"intervention count mismatch: {after} != {expected_interventions}"


if __name__ == "__main__":
    asyncio.run(reseed())