"""Finding-driven S0–S4 safety. Hypotheses and Google diagnoses cannot escalate."""

from app.discovery.orchestrator import orchestrate
from app.discovery.safety import assess_safety, extract_safety_findings, screen_safety


CASE_A = "My right side hurts under my ribs sometimes after eating. Been happening six months."
CASE_B = "Severe right upper pain for eight hours, can't stop vomiting and I'm running a fever."
CASE_C = "My gallbladder hurts."
CASE_D = "I think I have sepsis because Google said so."
CASE_FOLLOW = (
    "Right under my ribs. Usually 20–30 minutes after fatty food. Maybe a 4/10. "
    "Goes away in an hour. No fever or vomiting. This has been happening for seven months."
)
HISTORICAL = "Five years ago I had jaundice, but today I just have occasional mild discomfort."
NEGATED = "No fever, vomiting, or yellowing."
CHRONIC_WEAK = "I've felt generally weak for a year."
FOCAL_ARM = "My left arm suddenly won't move."
BURNING = "For six months, my feet have burned at night. My doctor says my blood work is normal."
CHEST = "I have crushing chest pain, I'm sweating, struggling to breathe and feel like I'm going to pass out."


def test_disposition_is_five_levels_not_binary():
    assert screen_safety(CASE_C).status == "S1"
    assert screen_safety(CASE_B).status == "S4"
    assert screen_safety(BURNING).status == "S2"
    assert "urgent" != screen_safety(CASE_C).status
    assert "safe" != screen_safety(CASE_C).status


def test_case_a_incomplete_not_emergency():
    result = orchestrate(CASE_A, prior_facts={}, asked=[], answered=set())
    assert result.safety_status == "S1"
    assert result.action.type != "show_safety_message"
    assert result.discovery_can_continue is True
    assert result.action.type == "ask_question"
    assert (result.action.question_id or "").startswith("q_safety_")
    assert "cholecystitis" not in result.message.lower()
    assert "you have" not in result.message.lower()


def test_case_b_emergency_overrides_discovery():
    result = orchestrate(CASE_B, prior_facts={}, asked=[], answered=set())
    assert result.safety_status == "S4"
    assert result.action.type == "show_safety_message"
    assert result.safety_override is True
    assert result.discovery_can_continue is False
    assert "urgent" in result.message.lower()
    assert "cholecystitis" not in result.message.lower()
    assert "you have" not in result.message.lower()


def test_case_c_gallbladder_is_interpretation_and_s1():
    result = orchestrate(CASE_C, prior_facts={}, asked=[], answered=set())
    assert result.safety_status == "S1"
    names = {item.name: item.value for item in result.new_findings}
    assert names.get("patient_interpretation") == "biliary_source"
    assert result.action.type != "show_safety_message"
    assert "gallbladder pain" in result.message.lower() or "where you're feeling" in result.message.lower()
    assert "cholecystitis" not in result.message.lower()


def test_case_d_does_not_inherit_google_diagnosis():
    result = orchestrate(CASE_D, prior_facts={}, asked=[], answered=set())
    assert result.safety_status in {"S0", "S1"}
    assert result.action.type != "show_safety_message"
    blob = result.message.lower()
    assert "sepsis" not in blob
    assert "you have" not in blob
    assert any(item.name == "patient_interpretation" and item.value == "sepsis" for item in result.new_findings)


def test_followup_chronic_pattern_continues_discovery():
    first = orchestrate(CASE_C, prior_facts={}, asked=[], answered=set())
    prior = {item.name: item.value or "reported" for item in first.new_findings}
    asked = [first.action.question_id] if first.action.question_id else []
    second = orchestrate(CASE_FOLLOW, prior_facts=prior, asked=asked, answered=set())
    assert second.safety_status == "S2"
    assert second.discovery_can_continue is True
    assert second.action.type != "show_safety_message"
    names = {item.name: item.value for item in second.new_findings}
    assert names.get("fever") == "absent"
    assert names.get("vomiting") == "absent"


def test_historical_jaundice_does_not_make_an_emergency():
    result = orchestrate(HISTORICAL, prior_facts={}, asked=[], answered=set())
    assert result.safety_status != "S4"
    findings = extract_safety_findings(HISTORICAL)
    jaundice = next(item for item in findings if item.concept == "jaundice")
    assert jaundice.temporality == "historical"
    assert result.action.type != "show_safety_message"


def test_gallbladder_is_not_a_sphincter_finding():
    from app.discovery.intake import extract_facts
    from app.discovery.safety import extract_safety_findings

    for text in (
        "I think it's my gallbladder because fatty food makes it worse.",
        "Pain in my gall bladder after fatty food.",
    ):
        assert not any(item.name == "sphincter change" for item in extract_facts(text)), text
        assert not any(item.concept == "sphincter_change" for item in extract_safety_findings(text)), text


def test_recent_hours_are_not_historical():
    result = orchestrate(
        "In the past two hours I have crushing chest pain, I'm sweating, and struggling to breathe.",
        prior_facts={},
        asked=[],
        answered=set(),
    )
    assert result.safety_status == "S4"


def test_no_fever_does_not_wipe_vomiting():
    findings = extract_safety_findings("I have no fever, just vomiting I can't stop.")
    by_name = {item.concept: item for item in findings}
    assert by_name["fever"].presence == "absent"
    assert by_name["vomiting"].presence == "present"
    assert by_name["vomiting"].qualifier == "repeated"


def test_followup_does_not_undo_emergency():
    first = orchestrate(CASE_B, prior_facts={}, asked=[], answered=set())
    assert first.safety_status == "S4"
    prior = {item.name: item.value or "reported" for item in first.new_findings}
    second = orchestrate("What should I do?", prior_facts=prior, asked=[], answered=set())
    assert second.safety_status == "S4"
    assert second.discovery_can_continue is False
    assert second.action.type == "show_safety_message"


def test_explicit_negatives_are_stored():
    findings = extract_safety_findings(NEGATED)
    by_name = {item.concept: item.presence for item in findings}
    assert by_name["fever"] == "absent"
    assert by_name["vomiting"] == "absent"
    assert by_name["jaundice"] == "absent"


def test_chronic_generalized_weakness_is_not_an_emergency():
    result = orchestrate(CHRONIC_WEAK, prior_facts={}, asked=[], answered=set())
    assert result.safety_status != "S4"
    assert result.action.type != "show_safety_message"


def test_sudden_focal_arm_weakness_is_s4():
    result = orchestrate(FOCAL_ARM, prior_facts={}, asked=[], answered=set())
    assert result.safety_status == "S4"
    assert result.action.type == "show_safety_message"


def test_crushing_chest_constellation_does_not_ask_a_scale():
    result = orchestrate(CHEST, prior_facts={}, asked=[], answered=set())
    assert result.safety_status == "S4"
    assert result.action.type == "show_safety_message"
    assert "1-10" not in result.message.lower()
    assert "scale" not in result.message.lower()


def test_hypothesis_cannot_escalate():
    findings = extract_safety_findings("Possible sphincter dysfunction.")
    assessment = assess_safety(findings)
    assert assessment.state != "S4"
    assert not any(item.kind == "hypothesis" and item.presence == "present" for item in findings)


def test_burning_feet_still_asks_laterality():
    result = orchestrate(BURNING, prior_facts={}, asked=[], answered=set())
    assert result.safety_status == "S2"
    assert result.action.question_id == "q_laterality"
    assert result.discovery_can_continue is True


def test_safety_net_is_contextual_not_generic_chest():
    result = orchestrate(CASE_A, prior_facts={}, asked=[], answered=set())
    net = result.safety.get("safety_net") or {}
    watch = " ".join(net.get("watch_for") or []).lower()
    assert "vomiting" in watch or "yellowing" in watch
    assert "call 911" not in watch


NATASHA_PRIOR = {
    "abdominal_pain": "location_unclear",
    "patient_interpretation": "biliary_source",
    "chronology": "chronic",
}
NATASHA_TURN = (
    "no none of that just intermittent, i can eat fat but i sometimes feel like throwing up"
)


def test_none_of_that_closes_the_systemic_screen():
    findings = extract_safety_findings(
        NATASHA_TURN,
        extract_safety_findings("My gallbladder hurts."),
        current_closes="fever",
    )
    by_name = {item.concept: item for item in findings}
    assert by_name["fever"].presence == "absent"
    assert by_name["vomiting"].presence == "absent"
    assert by_name["jaundice"].presence == "absent"
    assert by_name["nausea"].presence == "present"
    assert by_name["fatty_food_trigger"].presence == "absent"
    assert by_name["nausea"].trajectory == "intermittent_stable"


def test_nope_none_of_that_also_closes_the_screen():
    findings = extract_safety_findings("nope none of that", current_closes="systemic_red_flags")
    by_name = {item.concept: item.presence for item in findings}
    assert by_name["fever"] == "absent"
    assert by_name["vomiting"] == "absent"
    assert by_name["jaundice"] == "absent"


def test_feel_like_throwing_up_is_nausea_not_vomiting():
    findings = extract_safety_findings("i sometimes feel like throwing up")
    by_name = {item.concept: item for item in findings}
    assert by_name["nausea"].presence == "present"
    assert "vomiting" not in by_name or by_name["vomiting"].presence != "present"


def test_answered_safety_screen_moves_to_gi_discriminator():
    first = orchestrate("My gallbladder hurts.", prior_facts={}, asked=[], answered=set())
    prior = {**NATASHA_PRIOR, **{item.name: item.value or "reported" for item in first.new_findings}}
    asked = [first.action.question_id] if first.action.question_id else ["q_safety_systemic"]
    second = orchestrate(
        NATASHA_TURN,
        prior_facts=prior,
        asked=asked,
        answered=set(),
        current_closes="fever",
    )
    assert second.safety_status in {"S1", "S2"}
    assert second.action.type != "show_safety_message"
    prompt = (second.action.prompt or second.message or "").lower()
    assert "yellowing" not in prompt
    assert "repeated vomiting" not in prompt
    names = {item.name: item.value for item in second.new_findings}
    assert names.get("fever") == "absent"
    assert names.get("nausea") == "reported" or names.get("nausea") == "present"
    assert names.get("fatty_food") == "tolerated" or names.get("fatty_food_trigger") == "absent"


def test_abdominal_case_does_not_ask_foot_laterality():
    result = orchestrate(
        "The queasiness is still just intermittent and I can eat fat.",
        prior_facts={
            **NATASHA_PRIOR,
            "fever": "absent",
            "vomiting": "absent",
            "jaundice": "absent",
            "nausea": "reported",
            "trajectory": "intermittent_stable",
            "severity": "mild_to_moderate",
            "chronology": "chronic",
        },
        asked=["q_safety_systemic", "q_safety_fever"],
        answered={"fever", "vomiting", "jaundice"},
    )
    assert result.action.question_id != "q_laterality"
    assert result.action.question_id != "q_weakness_safety"
    assert (result.action.question_id or "").startswith("q_gi_")
    prompt = (result.action.prompt or "").lower()
    assert "both feet" not in prompt
    assert "weakness" not in prompt
