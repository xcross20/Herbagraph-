"""Open-world observation ingestion. User wording is provenance, not system truth."""

from __future__ import annotations

import hashlib
import re


PHENOMENA = (
    ("crawling_sensation", re.compile(r"crawl|creep")),
    ("itch", re.compile(r"itch|itchy|prurit")),
    ("burning", re.compile(r"burn(?:ed|ing)?")),
    ("pain", re.compile(r"pain|hurt|ache|discomfort")),
    ("shoulder_pain", re.compile(r"shoulder")),
)

SITES = (
    ("ruq", re.compile(r"under (?:the |my )?(?:right )?ribs|right upper|\bruq\b")),
    ("genital_or_reproductive_area", re.compile(r"reproductive|genital|groin|pelvic")),
    ("shoulder", re.compile(r"shoulder")),
    ("stomach", re.compile(r"\bstomach\b|epigastric")),
    ("feet", re.compile(r"\bfeet\b|\bfoot\b")),
    ("face", re.compile(r"face|facial")),
)

NEGATIVES = (
    ("swelling", re.compile(r"no (?:visible )?swell|without swell|not swollen")),
    ("redness", re.compile(r"no redness|not red|without redness")),
    ("warmth", re.compile(r"no warmth|not warm|without warmth")),
)


def _oid(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def extract_observations(text: str) -> list[dict]:
    blob = text or ""
    lowered = blob.lower()
    rows: list[dict] = []
    for phenomenon, pattern in PHENOMENA:
        if not pattern.search(lowered):
            continue
        sites = [(code, "stated") for code, site_pat in SITES if site_pat.search(lowered)]
        if phenomenon == "shoulder_pain":
            sites = [("shoulder", "stated")]
        if not sites:
            sites = [("unresolved", "uncertain")]
        negatives = [name for name, pat in NEGATIVES if pat.search(lowered)]
        for site, certainty in sites:
            if site == "genital_or_reproductive_area":
                certainty = "uncertain"
            surface = "uncertain"
            rows.append(
                {
                    "id": _oid(phenomenon, site, blob[:80]),
                    "wording_hash": _oid("w", blob),
                    "phenomenon": phenomenon,
                    "site": site,
                    "site_certainty": certainty,
                    "surface": surface,
                    "negatives": negatives,
                    "novelty": "unresolved",
                }
            )
    if re.search(r"juice fast|fasting.{0,20}juice|juice.{0,20}improv", lowered):
        rows.append(
            {
                "id": _oid("juice_fast_improves", "ruq", "assoc"),
                "wording_hash": _oid("w", blob),
                "phenomenon": "reported_improvement_with_juice_fast",
                "site": "ruq",
                "site_certainty": "stated",
                "surface": "internal",
                "negatives": [],
                "association": "patient_reported",
                "novelty": "unresolved",
            }
        )
    if re.search(r"popcorn", lowered):
        rows.append(
            {
                "id": _oid("popcorn_trigger", "stomach", "assoc"),
                "wording_hash": _oid("w", blob),
                "phenomenon": "reported_trigger_popcorn",
                "site": "stomach" if "stomach" in lowered else "unresolved",
                "site_certainty": "stated" if "stomach" in lowered else "uncertain",
                "surface": "internal",
                "negatives": [],
                "association": "patient_reported",
                "novelty": "unresolved",
            }
        )
    return rows


def classify_novelty(existing: list[dict], incoming: dict) -> str:
    for item in existing:
        if item.get("phenomenon") == incoming.get("phenomenon") and item.get("site") == incoming.get("site"):
            extra = set(incoming.get("negatives") or []) - set(item.get("negatives") or [])
            return "refinement" if extra else "duplicate"
    if incoming.get("site") in {item.get("site") for item in existing}:
        return "novel_same_branch"
    return "novel_new_branch"


def merge_observations(existing: list[dict], incoming: list[dict]) -> list[dict]:
    held = [dict(item) for item in existing]
    for item in incoming:
        novelty = classify_novelty(held, item)
        item = {**item, "novelty": novelty}
        if novelty == "duplicate":
            continue
        if novelty == "refinement":
            for row in held:
                if row.get("phenomenon") == item.get("phenomenon") and row.get("site") == item.get("site"):
                    row["negatives"] = sorted(set(row.get("negatives") or []) | set(item.get("negatives") or []))
                    row["novelty"] = "refinement"
                    break
            continue
        held.append(item)
    return held


def location_must_not_become_epigastric(prior_location: str | None, incoming_value: str | None) -> str | None:
    """Keep stated RUQ location. Do not silently rewrite it to epigastric."""
    if prior_location == "ruq" and incoming_value == "epigastric":
        return "ruq"
    return incoming_value


def observation_summary(rows: list[dict]) -> str:
    bits = []
    for item in rows:
        site = (item.get("site") or "unresolved").replace("_", " ")
        if item.get("site_certainty") == "uncertain":
            site = f"{site} (uncertain surface/depth)"
        bits.append(f"{(item.get('phenomenon') or 'sensation').replace('_', ' ')} at {site}")
    return "; ".join(bits[:6])
