"""API-imported intervention candidates.

Populated by `scripts/import_interventions_from_apis.py` from USDA FoodData Central,
PubChem autocomplete, and ClinicalTrials.gov intervention lists.

Rules:
  - Machine-generated; do not hand-edit large batches here.
  - Prefer Tier A / curated catalogs when names collide (merge order).
  - Evidence claims are NOT invented here — run PMID growth after import.
"""

from __future__ import annotations

# Empty until the first successful --write import run.
API_IMPORTED_INTERVENTIONS: list[dict] = []
