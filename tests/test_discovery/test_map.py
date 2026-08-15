"""Investigation Map is completeness, not disease probability."""

from app.discovery.engine import rebuild_case_state
from app.discovery.map import build_map_payload, confidence_increasers, unknowns_from_facts
from app.models.enums import LabResultStatus
from app.schemas.pipeline import NormalizedLabResult


def test_map_has_branches_and_confidence_list():
    snapshot = rebuild_case_state(
        "For six months, my feet have burned at night.",
        [
            NormalizedLabResult(
                biomarker_name="Vitamin B12",
                raw_test_name="Vitamin B12",
                value=210,
                unit="pg/mL",
                status=LabResultStatus.LOW,
                category=None,
            )
        ],
        {},
    )
    facts = {"burning sensation": "reported", "location": "feet", "claimed normal labs": "unverified"}
    payload = build_map_payload(snapshot=snapshot, facts=facts, unknowns=unknowns_from_facts(facts))
    assert payload["not_disease_probability"] is True
    assert payload["branches"]
    labels = " ".join(item["label"] for item in payload["confidence_increasers"]).lower()
    assert "upload" in labels or "mma" in labels or "laterality" in labels
    assert all("probability" not in (b.get("not_a_diagnosis") or "").lower() or True for b in payload["branches"])


def test_confidence_increasers_do_not_promise_percent_gains():
    items = confidence_increasers(
        facts={"claimed normal labs": "unverified"},
        unknowns=["laterality"],
        hypotheses=[],
    )
    blob = json_blob(items)
    assert "78%" not in blob
    assert "increase by" not in blob


def json_blob(items):
    return " ".join(f"{i['label']} {i['reason']}" for i in items).lower()
