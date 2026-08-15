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


def test_last_visit_opener_from_snapshot():
    from app.discovery.context import last_visit_from_snapshot, last_visit_opener

    visit = last_visit_from_snapshot(
        {
            "current_concerns": ["recurrent right-upper abdominal pain"],
            "other_diagnostics": ["emg testing: reported_normal"],
            "lab_trends": [{"name": "Vitamin B12", "value": "210"}],
        }
    )
    assert visit["has_history"] is True
    text = last_visit_opener(visit)
    assert "Last time we were looking at" in text
    assert "has anything changed" in text.lower()


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


def test_person_package_omits_generic_names():
    from app.discovery.context import person_package

    for name in ("", "Patient", "Self", "there", "  patient  "):
        pkg = person_package(
            display_name=name,
            snapshot_payload={},
            prior_facts={},
            last_visit={},
        )
        assert pkg["first_name"] == ""


def test_person_package_is_compact_and_skips_safety():
    from app.discovery.context import person_package

    pkg = person_package(
        display_name="Maya Chen",
        snapshot_payload={
            "current_concerns": ["burning feet at night"],
            "lab_trends": [{"name": "Vitamin B12", "value": 210, "status": "low"}],
            "medications": ["metformin"],
        },
        prior_facts={"safety_state": "S1", "burning": "night"},
        last_visit={"has_history": True, "summary": "burning feet at night"},
        age=54,
        biological_sex="female",
    )
    assert pkg["first_name"] == "Maya"
    assert pkg["age"] == 54
    assert pkg["biological_sex"] == "female"
    assert pkg["concerns"] == ["burning feet at night"]
    assert pkg["labs"][0]["name"] == "Vitamin B12"
    assert pkg["meds"] == ["metformin"]
    assert pkg["last_visit"]["summary"] == "burning feet at night"
    assert not any("safety_state" in item for item in pkg["known"])
    assert any(item.startswith("burning:") for item in pkg["known"])


def test_person_package_drops_impossible_age():
    from app.discovery.context import person_package

    pkg = person_package(
        display_name="Maya",
        snapshot_payload={},
        prior_facts={},
        last_visit={},
        age=240,
        biological_sex="  ",
    )
    assert pkg["age"] is None
    assert pkg["biological_sex"] is None
