#!/usr/bin/env python3
"""Remap persisted lab_results rows to catalog canonical biomarker names."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app import database
from app.models.lab import LabResult
from app.models.user import HealthProfile
from app.pipeline.biomarker_normalizer import normalized_result_from_lab_result
from app.pipeline.user_biomarker_profile import is_catalog_biomarker, prune_custom_biomarkers_overlapping_catalog


def remap_all() -> dict:
    session = database.get_sync_db()
    updated = 0
    try:
        profiles = {
            str(p.user_id): list(p.custom_biomarkers or [])
            for p in session.execute(select(HealthProfile)).scalars().all()
        }

        for profile_user_id, custom in profiles.items():
            pruned = prune_custom_biomarkers_overlapping_catalog(custom)
            if pruned != custom:
                profile = session.execute(
                    select(HealthProfile).where(HealthProfile.user_id == profile_user_id)
                ).scalar_one()
                profile.custom_biomarkers = pruned
                session.add(profile)

        for row in session.execute(
            select(LabResult).options(joinedload(LabResult.lab_report))
        ).scalars().all():
            user_id = str(row.lab_report.user_id) if row.lab_report else None
            custom = profiles.get(user_id or "", [])
            normalized = normalized_result_from_lab_result(row, custom_biomarkers=custom)
            if normalized.biomarker_name == row.biomarker_name and normalized.status == row.status:
                continue
            row.biomarker_name = normalized.biomarker_name
            row.reference_range_low = normalized.reference_range_low
            row.reference_range_high = normalized.reference_range_high
            row.status = normalized.status
            session.add(row)
            updated += 1

        session.commit()
        return {"updated_rows": updated}
    finally:
        session.close()


if __name__ == "__main__":
    result = remap_all()
    print(f"Remapped {result['updated_rows']} lab_result rows.")