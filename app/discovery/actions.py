"""Next-best-action engine. The conversation layer does not pick these."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CatalogQuestion:
    code: str
    prompt: str
    closes: str
    kind: str
    purpose: str
    options: tuple[str, ...] = ()
    interaction: str = "yes_no"
    gain: float = 0.5


QUESTIONS: tuple[CatalogQuestion, ...] = (
    CatalogQuestion(
        "q_weakness_safety",
        "Have you noticed new weakness, such as a foot that will not lift?",
        "weakness",
        "safety",
        "Screen for urgent focal weakness.",
        ("Yes", "No", "Not sure"),
        "single_select",
        0.95,
    ),
    CatalogQuestion(
        "q_laterality",
        "Is the burning happening in both feet, or mainly one?",
        "laterality",
        "discriminating",
        "Determine whether the pattern is length-dependent or focal.",
        ("Left", "Right", "Both", "Changes sides", "Not sure"),
        "single_select",
        0.88,
    ),
    CatalogQuestion(
        "q_distribution",
        "Does it stay mostly in the toes and soles, or has it moved above the ankles?",
        "distribution",
        "discriminating",
        "Separate distal sensory pattern from proximal extension.",
        ("Toes and soles", "Above the ankles", "Not sure"),
        "single_select",
        0.80,
    ),
    CatalogQuestion(
        "q_temperature",
        "Do you also notice numbness, pins-and-needles, or trouble telling hot from cold?",
        "temperature sensation",
        "discriminating",
        "Ask whether small-fiber sensory qualities are present — not to diagnose them.",
        ("Yes", "No", "Not sure"),
        "single_select",
        0.78,
    ),
    CatalogQuestion(
        "q_prior_workup",
        "Have you already had testing specifically for this — labs, EMG, or imaging?",
        "prior_workup",
        "completion",
        "Ask what has already been evaluated before recommending new tests.",
        ("Labs", "EMG or nerve conduction", "Imaging", "None that I know of", "Not sure"),
        "single_select",
        0.68,
    ),
    CatalogQuestion(
        "q_emg",
        "Have you ever had an EMG or nerve-conduction study for this?",
        "emg_status",
        "completion",
        "Learn whether large-fiber testing was already done.",
        ("Yes", "No", "Not sure"),
        "single_select",
        0.62,
    ),
    CatalogQuestion(
        "q_medications",
        "Are you taking metformin, a PPI, or another long-term medication?",
        "medications",
        "completion",
        "Case-completion: B12-relevant medications.",
        (),
        "yes_no",
        0.45,
    ),
    CatalogQuestion(
        "q_gi_location",
        "When that feeling shows up, where do you notice it most — under the right ribs, the pit of the stomach, or more like a wave of queasiness without a clear spot?",
        "pain_location",
        "discriminating",
        "Separate right-upper, epigastric, and nausea-predominant patterns without diagnosing.",
        ("Under the right ribs", "Pit of the stomach", "Mostly nausea, no clear spot", "It moves around", "Not sure"),
        "single_select",
        0.87,
    ),
    CatalogQuestion(
        "q_gi_episode",
        "When it comes, does it last minutes, an hour or two, or linger most of the day?",
        "episode_duration",
        "discriminating",
        "Episode length helps separate colicky from lingering dyspeptic patterns.",
        ("Minutes", "An hour or two", "Most of the day", "Not sure"),
        "single_select",
        0.84,
    ),
    CatalogQuestion(
        "q_gi_meal",
        "Is it tied to eating — right after meals, a while after, or not obviously related?",
        "meal_relation",
        "discriminating",
        "Meal timing is a discriminator between biliary-type, gastric, and reflux-type branches.",
        ("Right after eating", "An hour or more after", "Not related to food", "Not sure"),
        "single_select",
        0.83,
    ),
)


@dataclass
class NextAction:
    type: str
    objective: str
    question_id: str | None = None
    prompt: str | None = None
    interaction: dict | None = None
    score: float = 0.0
    extras: dict = field(default_factory=dict)


def _asked_or_answered(question: CatalogQuestion, asked: set[str], facts: dict[str, str], answered: set[str]) -> bool:
    if question.code in asked:
        return True
    if question.closes in facts or question.closes in answered:
        return True
    return False


def generate_actions(
    *,
    facts: dict[str, str],
    asked: set[str],
    answered: set[str],
    contradictions: list[str],
    safety_status: str,
    hypotheses: list,
    turn_count: int,
    wants_evidence: bool = False,
    safety: Any | None = None,
    guide_actions: list | None = None,
) -> list[NextAction]:
    from app.discovery.safety import normalize_state

    actions: list[NextAction] = []
    state = safety.state if safety is not None else normalize_state(safety_status)
    if state == "S4":
        return [
            NextAction(
                type="show_safety_message",
                objective="Pause discovery for urgent in-person evaluation.",
                score=1.0,
            )
        ]
    if state == "S3":
        limited = [
            NextAction(
                type="advise_prompt_evaluation",
                objective="Advise prompt in-person assessment. Limited continuation only.",
                prompt=(safety.message if safety is not None else None),
                score=0.99,
            )
        ]
        if wants_evidence:
            limited.append(
                NextAction(
                    type="retrieve_evidence",
                    objective="Attach retrieved PubMed citations to the Case. Do not invent PMIDs.",
                    prompt="I can attach retrieved literature. Citations only come from PubMed. This is not a diagnosis.",
                    score=0.5,
                )
            )
        return limited
    if state == "S1" and safety is not None:
        for index, item in enumerate(getattr(safety, "clarifiers", []) or []):
            if item.code in asked or item.closes in facts or item.closes in answered:
                continue
            if item.code == "q_safety_systemic" and asked & {"q_safety_fever", "q_safety_systemic"}:
                continue
            options = list(item.options)
            actions.append(
                NextAction(
                    type="ask_question",
                    objective="Clarify safety-discriminating facts before disposition.",
                    question_id=item.code,
                    prompt=item.prompt,
                    interaction={"type": "single_select", "options": options} if options else {"type": "yes_no", "options": ["Yes", "No", "Not sure"]},
                    score=0.96 - (index * 0.01),
                )
            )
    if wants_evidence and state != "S4":
        actions.append(
            NextAction(
                type="retrieve_evidence",
                objective="Attach retrieved PubMed citations to the Case. Do not invent PMIDs.",
                prompt=(
                    "I can attach retrieved literature to this Case. Citations only come from PubMed. "
                    "This is not a diagnosis."
                ),
                score=0.91,
            )
        )
    if contradictions:
        topic = contradictions[0]
        actions.append(
            NextAction(
                type="clarify",
                objective=f"Resolve a contradiction on {topic}.",
                prompt=(
                    f"Earlier I had {topic} as {facts.get(topic, 'something else')}. "
                    "That does not match what you just said. Which is the usual pattern?"
                ),
                score=0.97,
                extras={"topic": topic},
            )
        )

    from app.discovery.intake import is_abdominal_case

    neuro = "burning sensation" in facts or facts.get("location") == "feet"
    abdominal = is_abdominal_case(facts)
    for question in QUESTIONS:
        if _asked_or_answered(question, asked, facts, answered):
            continue
        if question.code.startswith("q_gi_") and not abdominal:
            continue
        if question.code.startswith("q_gi_") and state == "S1":
            continue
        if abdominal and question.code in {
            "q_laterality",
            "q_distribution",
            "q_temperature",
            "q_weakness_safety",
            "q_emg",
            "q_medications",
        }:
            continue
        if question.kind == "safety" and state in {"S0", "S2", "routine"}:
            continue
        if question.kind == "safety" and not neuro:
            continue
        if question.code == "q_laterality" and facts.get("location") != "feet" and "burning sensation" not in facts:
            continue
        if question.code == "q_distribution" and "laterality" not in facts:
            continue
        if question.code == "q_temperature" and "laterality" not in facts:
            continue
        if question.code == "q_prior_workup" and "laterality" not in facts:
            continue
        if question.code == "q_emg" and "laterality" not in facts:
            continue
        interaction = None
        if question.interaction == "single_select" and question.options:
            interaction = {"type": "single_select", "options": list(question.options)}
        elif question.interaction == "yes_no":
            interaction = {"type": "yes_no", "options": ["Yes", "No", "Not sure"]}
        actions.append(
            NextAction(
                type="ask_question",
                objective=question.purpose,
                question_id=question.code,
                prompt=question.prompt,
                interaction=interaction,
                score=question.gain,
            )
        )

    emg = facts.get("emg testing")
    if emg in {"mentioned", "reported_normal", "reported_abnormal"} and "emg_report" not in facts:
        actions.append(
            NextAction(
                type="request_record",
                objective="Verify what an EMG actually tested, not only what was recalled.",
                prompt=(
                    "A recalled EMG result is useful, but it is unverified. "
                    "If you have the report, uploading it would let HerbaGraph confirm what was actually evaluated. "
                    "This is not a diagnosis."
                ),
                interaction={"type": "file_upload", "accepted_types": ["pdf"]},
                score=0.84,
            )
        )

    if facts.get("claimed normal labs") == "unverified" and turn_count >= 3:
        actions.append(
            NextAction(
                type="transition_to_labs",
                objective="Bring claimed-normal labs into the lab engine as evidence.",
                prompt=(
                    "You mentioned blood work described as normal. Uploading those labs would let the existing "
                    "lab engine interpret them as evidence on this Case. Recollection is not the same as a result."
                ),
                interaction={"type": "file_upload", "accepted_types": ["pdf", "csv", "txt"]},
                score=0.70,
            )
        )

    pattern_facts = sum(1 for key in ("laterality", "distribution", "timing", "duration") if key in facts)
    if pattern_facts >= 3 and hypotheses and turn_count >= 3:
        actions.append(
            NextAction(
                type="show_investigation_map",
                objective="Show investigation branches and gaps. Not a diagnosis.",
                score=0.66,
            )
        )

    if turn_count >= 8 and all(_asked_or_answered(q, asked, facts, answered) for q in QUESTIONS if q.kind != "completion"):
        actions.append(
            NextAction(
                type="recommend_investigation",
                objective="Further history is unlikely to reduce meaningful uncertainty.",
                prompt=(
                    "Another history question is unlikely to clarify this much further. "
                    "The largest remaining gap is objective assessment of the open investigation branches. "
                    "That is not a diagnosis."
                ),
                score=0.72,
            )
        )

    systemic_prompt = "fever, repeated vomiting, or yellowing"
    for item in guide_actions or []:
        if item.question_id and item.question_id in asked:
            continue
        if item.type == "show_safety_message" and state not in {"S3", "S4"}:
            continue
        if item.prompt and any(existing.prompt == item.prompt for existing in actions):
            continue
        prompt_l = (item.prompt or "").lower()
        if systemic_prompt in prompt_l and (
            facts.get("fever") in {"absent", "no"} or asked & {"q_safety_fever", "q_safety_systemic"}
        ):
            continue
        actions.append(item)

    actions.sort(key=lambda item: item.score, reverse=True)
    return actions


def select_action(candidates: list[NextAction]) -> NextAction:
    if not candidates:
        return NextAction(
            type="summarize",
            objective="No higher-value action remains on this turn.",
            prompt="I have no further directed question on this Case. You can add a note or upload records. Still not a diagnosis.",
            score=0.1,
        )
    return candidates[0]
