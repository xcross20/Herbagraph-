"""Fail closed when the live schema cannot run Discovery."""

from __future__ import annotations

REQUIRED_COLUMNS = {
    "discovery_cases": ("control_json",),
    "discovery_findings": ("active", "source_event_id", "identity_key", "supersedes_finding_id"),
    "discovery_turns": ("idempotency_key",),
    "discovery_investigation_branches": ("prior_resolved_at", "prior_close_reason"),
    "discovery_evidence_edges": ("coverage_relation", "rule_version", "rationale", "evaluated_at"),
    "discovery_monitoring_events": ("causal_kind",),
    "discovery_evidence_gaps": ("active", "identity_key"),
    "discovery_workup_items": ("identity_key",),
}


def missing_discovery_schema(inspector) -> list[str]:
    missing: list[str] = []
    tables = set(inspector.get_table_names())
    for table, columns in REQUIRED_COLUMNS.items():
        if table not in tables:
            missing.append(f"table:{table}")
            continue
        present = {item["name"] for item in inspector.get_columns(table)}
        for column in columns:
            if column not in present:
                missing.append(f"{table}.{column}")
    return missing


def public_schema_error(exc: BaseException) -> str:
    text = str(exc)
    lowered = text.lower()
    if "undefinedcolumn" in lowered or "does not exist" in lowered:
        return "Discovery storage is behind the application. The database needs alembic upgrade head."
    if "multiple head revisions" in lowered:
        return "Discovery cannot migrate: Alembic has more than one head."
    if "sqlalchemy" in lowered or "asyncpg" in lowered:
        return "Discovery could not save this turn. The Case was not updated."
    return text
