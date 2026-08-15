"""Longitudinal snapshot is derived from labs and cases, not authored prose."""

from app.discovery.snapshot import prior_facts_from_snapshot, snapshot_from_records


def test_snapshot_payload_is_structured_not_a_diagnosis():
    payload = snapshot_from_records(
        concerns=["burning feet at night"],
        symptoms=["burning sensation: reported"],
        labs=[{"name": "Vitamin B12", "value": 210, "status": "low"}],
        medications=["metformin"],
        workup=["emg testing: reported_normal"],
    )
    assert payload["current_concerns"] == ["burning feet at night"]
    assert payload["lab_trends"][0]["name"] == "Vitamin B12"
    assert payload["medications"] == ["metformin"]
    assert "emg testing" in payload["other_diagnostics"][0]
    blob = " ".join(str(payload).lower() for _ in [0])
    assert "you have" not in blob
    assert "neuropathy" not in blob


def test_prior_facts_include_meds_and_labs():
    facts = prior_facts_from_snapshot(
        {
            "medications": ["metformin", "omeprazole"],
            "lab_trends": [{"name": "Vitamin B12", "value": "210"}],
        }
    )
    assert "metformin" in facts["medications"]
    assert facts["prior lab Vitamin B12"] == "210"
    assert "diagnosis" not in facts
