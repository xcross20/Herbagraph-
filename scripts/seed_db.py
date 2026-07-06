#!/usr/bin/env python
"""Populate the database with the canonical HerbaGraph knowledge graph.

Idempotent: exits early if biomarkers already exist.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.knowledge_graph.seeder import is_seeded, seed_knowledge_graph  # noqa: E402


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        if await is_seeded(db):
            print("Database already seeded. Skipping.")
            return

        counts = await seed_knowledge_graph(db)
        print(
            f"Seeded {counts['biomarkers']} biomarkers, {counts['pathways']} pathways, "
            f"{counts['interventions']} interventions, {counts['evidence_claims']} evidence claims, "
            f"{counts['food_compound_sources']} food-compound sources."
        )


if __name__ == "__main__":
    asyncio.run(seed())
