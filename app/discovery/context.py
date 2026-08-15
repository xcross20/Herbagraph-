"""Assemble a compact last-visit package. Do not dump the whole history."""

from __future__ import annotations


def last_visit_from_snapshot(payload: dict | None) -> dict:
    data = payload or {}
    concerns = [str(item) for item in (data.get("current_concerns") or []) if item]
    workup = [str(item) for item in (data.get("other_diagnostics") or []) if item]
    labs = data.get("lab_trends") or []
    lab_names = [str(row.get("name")) for row in labs if row.get("name")]
    summary = concerns[0] if concerns else ""
    if workup and summary:
        summary = f"{summary.rstrip('.')}. Prior workup still unverified: {workup[0]}"
    elif workup and not summary:
        summary = f"Prior workup on file: {workup[0]}"
    return {
        "has_history": bool(concerns or workup or lab_names),
        "summary": summary[:280],
        "concerns": concerns[:4],
        "unverified": workup[:6],
        "lab_names": lab_names[:8],
    }


def last_visit_from_case(*, problem: str | None, workup: list[dict], concern: str | None) -> dict:
    summary = (problem or concern or "").strip()
    unverified = [
        f"{item.get('name')}: {item.get('value')}"
        for item in workup
        if item.get("name")
    ]
    return {
        "has_history": bool(summary or unverified),
        "summary": summary[:280],
        "concerns": [concern] if concern else [],
        "unverified": unverified[:6],
        "lab_names": [],
    }


def person_package(
    *,
    display_name: str | None,
    snapshot_payload: dict | None,
    prior_facts: dict[str, str] | None,
    last_visit: dict | None,
    age: int | None = None,
    biological_sex: str | None = None,
) -> dict:
    """Compact, relevant-only context for a personal reply. Not the full chart."""
    snap = snapshot_payload or {}
    first = (display_name or "").strip().split(" ")[0]
    if first.lower() in {"", "patient", "self", "there"}:
        first = ""
    labs = []
    for row in (snap.get("lab_trends") or [])[:8]:
        name = str(row.get("name") or "")
        if not name:
            continue
        labs.append(
            {
                "name": name,
                "value": row.get("value"),
                "status": row.get("status"),
            }
        )
    meds = [str(item) for item in (snap.get("medications") or [])[:6] if item]
    concerns = [str(item) for item in (snap.get("current_concerns") or [])[:4] if item]
    known = []
    for key, value in (prior_facts or {}).items():
        if key in {"safety_state"}:
            continue
        known.append(f"{key}: {value}")
        if len(known) == 20:
            break
    held_age = age if isinstance(age, int) and 0 < age < 120 else None
    sex = (biological_sex or "").strip().lower() or None
    return {
        "first_name": first,
        "age": held_age,
        "biological_sex": sex,
        "concerns": concerns,
        "meds": meds,
        "labs": labs,
        "last_visit": last_visit or {},
        "known": known,
    }


def last_visit_opener(visit: dict) -> str:
    if not visit or not visit.get("has_history") or not visit.get("summary"):
        return ""
    return (
        f"Last time we were looking at {visit['summary'].rstrip('.')}. "
        "Before we continue, has anything changed since then? "
    )
