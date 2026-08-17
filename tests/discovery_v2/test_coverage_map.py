"""Coverage and map V2 claims."""

from app.coverage.evaluator import evaluate
from app.coverage.resolver import resolve_test
from app.discovery.guide import validate_plan
from app.discovery.map import build_map_payload_v2


def test_mri_coverage_depends_on_protocol():
    match = resolve_test("brain MRI")
    assert match is not None
    standard = evaluate(match.test_code, "internal_auditory_canal", "MRI_BRAIN_STANDARD")
    iac = evaluate(match.test_code, "internal_auditory_canal", "MRI_IAC_WWO")
    assert standard.relation == "does_not_directly_assess"
    assert iac.relation == "directly_assesses"


def test_map_v2_has_no_diagnostic_probability():
    payload = build_map_payload_v2(
        case_id="case-1",
        version=2,
        branches=[
            {
                "id": "b1",
                "code": "small_fiber_function",
                "label": "Small-fiber function",
                "status": "partially_evaluated",
                "investigation_relevance": 0.7,
                "coverage": 0.2,
                "coverage_confidence": 0.8,
            }
        ],
        evidence=[{"branch_code": "small_fiber_function", "relationship": "does_not_address", "rationale": "EMG"}],
        gaps=[
            {
                "branch_code": "small_fiber_function",
                "label": "Objective small-fiber evaluation",
                "description": "IENFD not done",
                "status": "open",
            }
        ],
    )
    blob = str(payload).lower()
    assert "diagnostic_certainty" not in blob
    assert "disease_probability" not in blob
    assert payload["investigation_only"] is True
    assert payload["branches"][0]["non_addressing_evidence"]
    assert payload["branches"][0]["open_gaps"]


def test_validate_plan_accepts_v2_fields():
    plan = validate_plan(
        {
            "reported_facts": [{"concept": "right facial pressure", "type": "symptom"}],
            "timeline_events": [{"label": "electrical injury", "date_text": "2024-03"}],
            "branch_updates": [{"branch_code": "small_fiber_function", "proposed_label": "Small-fiber", "operation": "OPEN"}],
            "tool_requests": [{"tool": "SEARCH_PUBMED", "reason": "unusual chronology"}],
            "corrections": [{"reason": "onset was before surgery"}],
        }
    )
    assert plan.timeline_events[0].label == "electrical injury"
    assert plan.branch_updates[0].operation == "OPEN"
    assert plan.tool_requests[0].tool == "SEARCH_PUBMED"
    assert plan.reported_findings
