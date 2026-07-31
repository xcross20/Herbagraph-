#!/usr/bin/env python
"""Bootstrap pathway MODULATES/TARGETS edges for the graph recommendation engine.

Run after canonical entity bootstrap:
  python scripts/bootstrap_canonical_registry.py
  python scripts/bootstrap_graph_edges.py
  railway run python scripts/bootstrap_graph_edges.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal  # noqa: E402
from app.knowledge_graph.graph_edge_seed import bootstrap_graph_modulation_edges  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as db:
        stats = await bootstrap_graph_modulation_edges(db)
    print("Graph modulation edge bootstrap complete:")
    for key, value in sorted(stats.items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
