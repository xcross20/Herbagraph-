#!/usr/bin/env python
"""Deep enrichment pass: enqueue Tier A/B entities missing external IDs, then process.

Usage:
  python scripts/deep_enrichment_pass.py
  python scripts/deep_enrichment_pass.py --limit 25 --batch 10
  railway run python scripts/deep_enrichment_pass.py --limit 40
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal  # noqa: E402
from app.knowledge_graph.enrichment_worker import (  # noqa: E402
    enqueue_missing_external_ids,
    run_enrichment_batch,
)


async def main(limit: int, batch: int) -> None:
    async with AsyncSessionLocal() as db:
        seed_stats = await enqueue_missing_external_ids(
            db, limit=limit, requested_by="deep_enrichment_pass", priority=40
        )
        print("Seed missing external IDs:")
        for key, value in seed_stats.items():
            print(f"  {key}: {value}")

        processed = await run_enrichment_batch(db, limit=batch)
        print(f"Processed queue items: {len(processed)}")
        for item in processed:
            print(f"  - {item.query_name}: {item.status} — {item.result_summary or item.error_message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep enrichment pass over canonical registry")
    parser.add_argument("--limit", type=int, default=40, help="Max entities to enqueue")
    parser.add_argument("--batch", type=int, default=10, help="Max queue items to process now")
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.batch))
