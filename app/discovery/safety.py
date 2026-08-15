"""Finding-driven Discovery safety. Disposition is not a diagnosis."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable

from app.discovery.intake import ExtractedFact


STATES = ("S0", "S1", "S2", "S3", "S4")
EVIDENCE = ("INSUFFICIENT", "POSSIBLE", "SUPPORTED", "STRONGLY_SUPPORTED")

_BANNED_COPY = (
    "you have",
    "you may have",
    "this confirms",
    "life-threatening",
    "sepsis",
    "cholecystitis",
    "appendicitis",
    "small-fiber",
    "neuropathy",
)

_ATTENTION_DOMAINS = frozenset({"upper_abdominal_pain", "chest", "inherited_label"})

_DATASETS = {
    "upper_abdominal_pain": ("severity", "duration", "trajectory", "fever", "vomiting", "jaundice"),
    "chest": ("severity", "dyspnea", "syncope", "sweating"),
    "inherited_label": ("severity", "fever", "trajectory"),
    "neuro_sensory": (),
    "general": (),
}

_WATCH = {
    "upper_abdominal_pain": (
        "rapid worsening",
        "severe persistent pain",
        "repeated vomiting",
        "fever",
        "yellowing of the eyes or skin",
    ),
    "chest": ("crushing chest pain", "trouble breathing", "fainting", "heavy sweating"),
    "neuro_sensory": ("new focal weakness", "inability to walk", "bladder or bowel change"),
    "inherited_label": ("rapid worsening", "fever", "fainting"),
    "general": ("rapid worsening", "new severe pain", "fainting"),
}


@dataclass
class SafetyFinding:
    concept: str
    presence: str = "present"
    temporality: str = "current"
    severity: str | None = None
    trajectory: str | None = None
    chronology: str | None = None
    qualifier: str | None = None
    kind: str = "finding"
    source: str = "reported"


@dataclass
class SafetyClarifier:
    code: str
    prompt: str
    closes: str
    options: tuple[str, ...] = ()


@dataclass
class SafetyAssessment:
    state: str
    evidence_status: str
    confidence: str
    confidence_reason: str
    override: bool
    discovery_can_continue: bool
    clinical_followup_needed: bool
    urgency: str
    domain: str
    missing: list[str] = field(default_factory=list)
    known: list[str] = field(default_factory=list)
    clarifiers: list[SafetyClarifier] = field(default_factory=list)
    findings: list[SafetyFinding] = field(default_factory=list)
    interpretations: list[SafetyFinding] = field(default_factory=list)
    safety_net: dict | None = None
    critic: str = "ok"
    recommended_action: str = "continue"
    message: str = ""
    preface: str = ""

    @property
    def status(self) -> str:
        return self.state

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["status"] = self.state
        return payload


def normalize_state(raw: str | None) -> str:
    value = (raw or "").strip()
    if value in STATES:
        return value
    if value == "urgent":
        return "S4"
    if value == "watch":
        return "S1"
    if value in {"routine", "safe"}:
        return "S2"
    return "S0"


def _add(rows: list[SafetyFinding], item: SafetyFinding) -> None:
    for existing in rows:
        if existing.concept == item.concept and existing.kind == item.kind:
            rows.remove(existing)
            break
    rows.append(item)


def extract_safety_findings(text: str, prior: Iterable[SafetyFinding] | None = None) -> list[SafetyFinding]:
    rows: list[SafetyFinding] = list(prior or [])
    blob = (text or "").lower()
    if not blob.strip():
        return rows

    historical = bool(re.search(r"\b(\d+\s+years? ago|years ago|in the past)\b", blob))
    temporality = "historical" if historical and not re.search(r"\btoday\b|\bnow\b|\bcurrently\b", blob) else "current"
    if re.search(r"\btoday\b|\bthis morning\b|\bnow\b|\bcurrently\b", blob):
        temporality = "current"

    chronology = "unknown"
    if re.search(r"\b(this morning|today|two hours|2 hours|eight hours|8 hours|suddenly)\b", blob):
        chronology = "acute"
    if re.search(r"\b(weeks?)\b", blob) and chronology == "unknown":
        chronology = "subacute"
    if re.search(r"\b(\d+\s+months?|months|years?|a year)\b", blob):
        chronology = "chronic"
    if chronology == "chronic" and re.search(r"\b(suddenly|dramatically worse|this morning)\b", blob):
        chronology = "acute_on_chronic"

    trajectory = None
    if re.search(r"dramatically worse|rapidly worse|getting worse|worsening", blob):
        trajectory = "progressive_rapid" if re.search(r"rapid|dramatic", blob) else "progressive_slow"
    elif re.search(r"\bsuddenly\b|this morning", blob):
        trajectory = "sudden"
    elif re.search(r"sometimes|comes and goes|goes away|intermittent|every few weeks", blob):
        trajectory = "intermittent_stable"
    elif re.search(r"\bstable\b|same for", blob):
        trajectory = "stable"

    severity = None
    if re.search(r"\bcrushing\b|\bsevere\b|\b10/10\b|\b9/10\b|\b8/10\b", blob):
        severity = "severe"
    elif re.search(r"\b([1-4])/10\b|\bmild\b|\bmoderate\b", blob):
        severity = "mild_to_moderate"

    def present(concept: str, **kwargs: str) -> None:
        _add(
            rows,
            SafetyFinding(
                concept=concept,
                presence="present",
                temporality=kwargs.get("temporality", temporality),
                severity=kwargs.get("severity", severity),
                trajectory=kwargs.get("trajectory", trajectory),
                chronology=kwargs.get("chronology", chronology if chronology != "unknown" else None),
                qualifier=kwargs.get("qualifier"),
                kind=kwargs.get("kind", "finding"),
            ),
        )

    def absent(concept: str) -> None:
        _add(rows, SafetyFinding(concept=concept, presence="absent", temporality="current", kind="finding"))

    if re.search(r"no fever|without fever|don't have fever|do not have fever", blob):
        absent("fever")
    elif re.search(r"\bfever\b|running a fever|febrile", blob):
        present("fever")

    if re.search(r"no vomiting|without vomiting|don't have vomiting|do not have vomiting|no .*vomiting", blob):
        absent("vomiting")
    elif re.search(r"can't stop vomiting|cannot stop vomiting|repeated vomiting|vomiting x|keep vomiting", blob):
        present("vomiting", qualifier="repeated")
    elif re.search(r"\bvomit", blob):
        present("vomiting", qualifier="single")

    if re.search(r"no yellowing|without yellowing|no jaundice|don't have .*yellow|\bno\b.{0,50}yellow", blob):
        absent("jaundice")
    elif re.search(r"\bjaundice\b|yellowing of (?:the )?(?:eyes|skin)|yellow (?:eyes|skin)", blob):
        jaund_temp = "historical" if re.search(r"years? ago.{0,40}jaundice|jaundice.{0,40}years? ago", blob) else temporality
        if historical and re.search(r"jaundice", blob) and re.search(r"years? ago", blob):
            jaund_temp = "historical"
        present("jaundice", temporality=jaund_temp)

    if re.search(r"gallbladder (?:pain|hurts)|pain where my gallbladder|i think (?:it'?s|its) (?:my )?gallbladder", blob):
        present("biliary_source", kind="interpretation")
        present("abdominal_pain", qualifier="location_unclear")
    if re.search(r"i think i have sepsis|google said.{0,60}sepsis", blob):
        present("sepsis", kind="interpretation")
    if re.search(r"appendix.{0,24}ruptur|i think.{0,24}appendicitis", blob):
        present("appendicitis", kind="interpretation")

    if re.search(r"right upper|under (?:my )?(?:right )?ribs|ruq|right side hurts under", blob):
        present("abdominal_pain", qualifier="ruq")
    elif re.search(r"\babdominal pain\b|\bstomach pain\b|\bbelly pain\b|mild discomfort|occasional mild", blob):
        present("abdominal_pain")
    if re.search(r"\bburn(?:ed|ing)?\b", blob) and re.search(r"\bfeet\b|\bfoot\b", blob):
        present("sensory_symptom")
    if re.search(r"none of those", blob):
        absent("fever")
        absent("vomiting")
        absent("jaundice")

    if re.search(r"crushing chest|chest pain", blob):
        qual = "crushing" if "crushing" in blob else None
        present("chest_pain", qualifier=qual, severity="severe" if qual else severity)
    if re.search(r"\bsweating\b|diaphore", blob):
        present("sweating")
    if re.search(r"struggling to breathe|short of breath|can't breathe|cannot breathe|\bdyspnea\b", blob):
        present("dyspnea")
    if re.search(r"pass out|passing out|syncope|\bfaint", blob):
        present("syncope")

    if re.search(r"can'?t lift|cannot lift|foot drop|won't move|will not move|arm suddenly", blob):
        present("weakness", qualifier="focal")
    elif re.search(r"generally weak|felt weak|feeling weak|weak for a (?:year|while)", blob):
        present("weakness", qualifier="generalized")
    elif re.search(r"\bnew weakness\b", blob):
        present("weakness", qualifier="focal")

    if re.search(r"bladder|bowel control", blob):
        present("sphincter_change")

    if re.search(r"can't keep (?:fluids|anything) down|unable to keep fluids", blob):
        present("vomiting", qualifier="repeated")

    if severity and any(item.concept in {"abdominal_pain", "chest_pain"} for item in rows):
        for item in rows:
            if item.concept in {"abdominal_pain", "chest_pain"} and item.presence == "present":
                item.severity = item.severity or severity
                item.trajectory = item.trajectory or trajectory
                item.chronology = item.chronology or (chronology if chronology != "unknown" else None)

    return rows


def findings_from_fact_map(facts: dict[str, str]) -> list[SafetyFinding]:
    rows: list[SafetyFinding] = []
    mapping = {
        "fever": "fever",
        "vomiting": "vomiting",
        "jaundice": "jaundice",
        "abdominal_pain": "abdominal_pain",
        "chest_pain": "chest_pain",
        "weakness": "weakness",
        "sphincter change": "sphincter_change",
        "dyspnea": "dyspnea",
        "syncope": "syncope",
        "sweating": "sweating",
        "patient_interpretation": None,
    }
    for key, concept in mapping.items():
        value = (facts.get(key) or "").lower()
        if not value:
            continue
        if key == "patient_interpretation":
            rows.append(SafetyFinding(concept=value, presence="present", kind="interpretation"))
            continue
        if concept is None:
            continue
        presence = "absent" if value in {"absent", "no", "none"} else "present"
        qualifier = None
        if concept == "vomiting" and value in {"repeated", "persistent"}:
            qualifier = "repeated"
        if concept == "weakness" and value in {"focal", "generalized", "reported"}:
            qualifier = "focal" if value in {"focal", "reported"} else "generalized"
        if concept == "abdominal_pain" and value in {"ruq", "location_unclear"}:
            qualifier = value
        rows.append(
            SafetyFinding(
                concept=concept,
                presence=presence,
                qualifier=qualifier,
                severity=facts.get("severity"),
                trajectory=facts.get("trajectory"),
                chronology=facts.get("chronology") or facts.get("duration"),
            )
        )
    if facts.get("onset") == "sudden":
        rows.append(SafetyFinding(concept="onset", presence="present", trajectory="sudden", chronology="acute"))
    if facts.get("location") in {"ruq", "abdomen"}:
        rows.append(SafetyFinding(concept="abdominal_pain", presence="present", qualifier=facts.get("location")))
    return rows


def safety_findings_to_facts(findings: list[SafetyFinding]) -> list[ExtractedFact]:
    extra: list[ExtractedFact] = []
    for item in findings:
        if item.kind == "interpretation":
            extra.append(ExtractedFact(name="patient_interpretation", value=item.concept, kind="context"))
            continue
        if item.kind != "finding":
            continue
        name = {"sphincter_change": "sphincter change"}.get(item.concept, item.concept)
        if item.presence == "absent":
            extra.append(ExtractedFact(name=name, value="absent", kind="assessment"))
        elif item.qualifier:
            extra.append(ExtractedFact(name=name, value=item.qualifier, kind="symptom"))
        else:
            extra.append(ExtractedFact(name=name, value="present", kind="symptom"))
        if item.severity:
            extra.append(ExtractedFact(name="severity", value=item.severity, kind="context"))
        if item.trajectory:
            extra.append(ExtractedFact(name="trajectory", value=item.trajectory, kind="context"))
        if item.chronology:
            extra.append(ExtractedFact(name="chronology", value=item.chronology, kind="context"))
    return extra


def _current(findings: list[SafetyFinding], concept: str) -> SafetyFinding | None:
    for item in findings:
        if item.concept == concept and item.kind == "finding" and item.temporality in {"current", "recent"}:
            return item
    return None


def _is_present(findings: list[SafetyFinding], concept: str) -> bool:
    item = _current(findings, concept)
    return item is not None and item.presence == "present"


def _is_absent(findings: list[SafetyFinding], concept: str) -> bool:
    item = _current(findings, concept)
    return item is not None and item.presence == "absent"


def _domain(findings: list[SafetyFinding]) -> str:
    concepts = {item.concept for item in findings}
    if "chest_pain" in concepts or "dyspnea" in concepts and "syncope" in concepts:
        return "chest"
    if "abdominal_pain" in concepts or "biliary_source" in concepts:
        return "upper_abdominal_pain"
    if concepts & {"sepsis", "appendicitis"} and any(i.kind == "interpretation" for i in findings):
        if not (_is_present(findings, "abdominal_pain") or _is_present(findings, "fever")):
            return "inherited_label"
    if concepts & {"weakness", "sensory_symptom"}:
        return "neuro_sensory"
    return "general"


def _known_unknown(findings: list[SafetyFinding], domain: str) -> tuple[list[str], list[str]]:
    required = list(_DATASETS.get(domain, ()))
    known: list[str] = []
    for item in findings:
        if item.kind != "finding":
            continue
        if item.concept in required and item.presence in {"present", "absent"}:
            known.append(item.concept)
        if item.severity and "severity" in required:
            known.append("severity")
        if (item.chronology or item.temporality) and "duration" in required:
            known.append("duration")
        if item.trajectory and "trajectory" in required:
            known.append("trajectory")
    known = list(dict.fromkeys(known))
    unknown = [name for name in required if name not in known]
    return known, unknown


def _clarifiers(domain: str, unknown: list[str]) -> list[SafetyClarifier]:
    catalog = {
        "severity": SafetyClarifier(
            "q_safety_severity",
            "Is the pain mild and intermittent, or severe and staying constant?",
            "severity",
            ("Mild / intermittent", "Moderate", "Severe and constant", "Not sure"),
        ),
        "duration": SafetyClarifier(
            "q_safety_duration",
            "How long has this pattern been going on — hours, weeks, or months?",
            "duration",
            ("Hours", "Days to weeks", "Months or longer", "Not sure"),
        ),
        "trajectory": SafetyClarifier(
            "q_safety_trajectory",
            "Is it staying about the same, coming and going, or rapidly getting worse?",
            "trajectory",
            ("Comes and goes", "About the same", "Slowly worse", "Rapidly worse", "Not sure"),
        ),
        "fever": SafetyClarifier(
            "q_safety_fever",
            "Are you having fever, repeated vomiting, or yellowing of the eyes or skin?",
            "fever",
            ("None of those", "Fever", "Repeated vomiting", "Yellowing", "Not sure"),
        ),
        "vomiting": SafetyClarifier(
            "q_safety_systemic",
            "Are you having fever, repeated vomiting, or yellowing of the eyes or skin?",
            "vomiting",
            ("None of those", "Fever", "Repeated vomiting", "Yellowing", "Not sure"),
        ),
        "jaundice": SafetyClarifier(
            "q_safety_systemic",
            "Are you having fever, repeated vomiting, or yellowing of the eyes or skin?",
            "jaundice",
            ("None of those", "Fever", "Repeated vomiting", "Yellowing", "Not sure"),
        ),
        "dyspnea": SafetyClarifier(
            "q_safety_chest",
            "Along with the chest discomfort, are you short of breath, sweating heavily, or feeling like you might pass out?",
            "dyspnea",
            ("No", "Trouble breathing", "Heavy sweating", "Nearly passing out", "Not sure"),
        ),
        "syncope": SafetyClarifier(
            "q_safety_chest",
            "Along with the chest discomfort, are you short of breath, sweating heavily, or feeling like you might pass out?",
            "syncope",
            ("No", "Trouble breathing", "Heavy sweating", "Nearly passing out", "Not sure"),
        ),
        "sweating": SafetyClarifier(
            "q_safety_chest",
            "Along with the chest discomfort, are you short of breath, sweating heavily, or feeling like you might pass out?",
            "sweating",
            ("No", "Trouble breathing", "Heavy sweating", "Nearly passing out", "Not sure"),
        ),
    }
    picked: list[SafetyClarifier] = []
    seen: set[str] = set()
    for name in unknown:
        item = catalog.get(name)
        if item is None or item.code in seen:
            continue
        seen.add(item.code)
        picked.append(item)
        if len(picked) == 3:
            break
    return picked


def _definite_emergency(findings: list[SafetyFinding]) -> bool:
    weakness = _current(findings, "weakness")
    onset_sudden = any(
        item.trajectory == "sudden" or item.chronology == "acute"
        for item in findings
        if item.presence == "present" and item.temporality in {"current", "recent"}
    )
    if (
        weakness
        and weakness.presence == "present"
        and weakness.qualifier == "focal"
        and weakness.temporality in {"current", "recent"}
        and onset_sudden
    ):
        return True
    chest = _current(findings, "chest_pain")
    if chest and chest.presence == "present" and chest.qualifier == "crushing":
        return True
    if chest and chest.presence == "present" and (
        _is_present(findings, "dyspnea") or _is_present(findings, "syncope") or _is_present(findings, "sweating")
    ):
        return True
    pain = _current(findings, "abdominal_pain")
    vomit = _current(findings, "vomiting")
    if (
        pain
        and pain.presence == "present"
        and pain.severity == "severe"
        and pain.temporality in {"current", "recent"}
        and vomit is not None
        and vomit.presence == "present"
        and vomit.qualifier == "repeated"
        and _is_present(findings, "fever")
    ):
        return True
    sphincter = _current(findings, "sphincter_change")
    if sphincter and sphincter.presence == "present" and onset_sudden:
        return True
    return False


def _significant_concerning(findings: list[SafetyFinding]) -> bool:
    pain = _current(findings, "abdominal_pain")
    if pain and pain.presence == "present" and pain.severity == "severe":
        vomit = _current(findings, "vomiting")
        if _is_present(findings, "fever") or (vomit is not None and vomit.presence == "present" and vomit.qualifier == "repeated"):
            return True
        if pain.trajectory == "progressive_rapid":
            return True
    weakness = _current(findings, "weakness")
    if weakness and weakness.presence == "present" and weakness.qualifier == "focal":
        return True
    chest = _current(findings, "chest_pain")
    if chest and chest.presence == "present" and chest.severity == "severe":
        return True
    return False


def _routine_pattern(findings: list[SafetyFinding]) -> bool:
    pain = _current(findings, "abdominal_pain")
    if pain and pain.presence == "present":
        chronic = pain.chronology == "chronic" or any(
            item.chronology == "chronic" for item in findings if item.temporality in {"current", "recent"}
        )
        intermittent = pain.trajectory in {"intermittent_stable", "stable"} or any(
            item.trajectory == "intermittent_stable" for item in findings
        )
        not_severe = pain.severity != "severe"
        systems_clear = _is_absent(findings, "fever") or _is_absent(findings, "vomiting")
        if chronic and intermittent and not_severe and systems_clear:
            return True
    weakness = _current(findings, "weakness")
    if weakness and weakness.qualifier == "generalized" and weakness.chronology == "chronic":
        return True
    if any(item.chronology == "chronic" for item in findings) and not _is_present(findings, "chest_pain"):
        if not _is_present(findings, "abdominal_pain"):
            return True
    return False


def _uses_only_interpretations(findings: list[SafetyFinding]) -> bool:
    presents = [item for item in findings if item.kind == "finding" and item.presence == "present"]
    interpretations = [item for item in findings if item.kind == "interpretation"]
    return bool(interpretations) and not any(
        item.concept not in {"abdominal_pain"} or item.qualifier != "location_unclear" for item in presents
    )


def critique(assessment: SafetyAssessment) -> SafetyAssessment:
    if assessment.state not in {"S3", "S4"}:
        return assessment
    findings = assessment.findings
    if _uses_only_interpretations(findings) or (
        assessment.interpretations and not any(i.presence == "present" and i.kind == "finding" and i.concept != "abdominal_pain" for i in findings)
        and not _definite_emergency(findings)
    ):
        if not _definite_emergency(findings):
            assessment.state = "S1"
            assessment.override = False
            assessment.discovery_can_continue = True
            assessment.urgency = "none"
            assessment.recommended_action = "clarify"
            assessment.critic = "downgraded: interpretation or hypothesis cannot escalate"
            assessment.evidence_status = "INSUFFICIENT"
            return assessment
    if any(item.concept == "jaundice" and item.temporality == "historical" for item in findings) and _definite_emergency(
        [item for item in findings if not (item.concept == "jaundice" and item.temporality == "historical")]
    ) is False and assessment.state == "S4":
        if not _definite_emergency([item for item in findings if item.temporality != "historical"]):
            assessment.state = "S1"
            assessment.override = False
            assessment.discovery_can_continue = True
            assessment.critic = "downgraded: historical finding was not current"
            assessment.recommended_action = "clarify"
    if _definite_emergency(findings):
        assessment.state = "S4"
        assessment.override = True
        assessment.discovery_can_continue = False
        assessment.urgency = "emergency"
        assessment.recommended_action = "emergency"
        if assessment.critic.startswith("downgraded"):
            assessment.critic = "ok: current emergency pattern holds"
    return assessment


def _preface(domain: str, state: str) -> str:
    if state == "S1" and domain == "upper_abdominal_pain":
        return (
            "When you say gallbladder pain, I want to separate where you're feeling it from what may be causing it."
        )
    if state == "S1" and domain == "inherited_label":
        return (
            "I'll go by the symptoms you are actually having, not the name that came up in a search."
        )
    if state == "S1":
        return "There are a few features I'd want to clarify before deciding whether this is appropriate to keep working through here."
    return ""


def _message(state: str, domain: str) -> str:
    if state == "S4":
        return (
            "Based on what you've shared so far, this needs urgent in-person evaluation rather than more Discovery questions. "
            "This is not a diagnosis."
        )
    if state == "S3":
        return (
            "Based on what you've shared so far, prompt in-person assessment would be the safer next step. "
            "I can keep a limited record of the pattern, but I will not continue a full investigation here. "
            "This is not a diagnosis."
        )
    if state == "S1":
        return _preface(domain, state)
    return ""


def assess_safety(
    findings: list[SafetyFinding],
    *,
    asked: set[str] | None = None,
) -> SafetyAssessment:
    asked = asked or set()
    interpretations = [item for item in findings if item.kind == "interpretation"]
    domain = _domain(findings)
    known, unknown = _known_unknown(findings, domain)
    clarifiers = [item for item in _clarifiers(domain, unknown) if item.code not in asked]

    if _definite_emergency(findings):
        state = "S4"
        evidence = "STRONGLY_SUPPORTED"
    elif _significant_concerning(findings):
        state = "S3"
        evidence = "SUPPORTED"
    elif _routine_pattern(findings):
        state = "S2"
        evidence = "SUPPORTED"
    elif domain in _ATTENTION_DOMAINS and unknown:
        state = "S1"
        evidence = "INSUFFICIENT"
    elif not findings:
        state = "S0"
        evidence = "INSUFFICIENT"
    else:
        state = "S2" if domain == "neuro_sensory" else ("S1" if unknown and domain in _ATTENTION_DOMAINS else "S0")
        evidence = "INSUFFICIENT" if unknown else "POSSIBLE"

    if state == "S1" and not clarifiers:
        state = "S2"

    assessment = SafetyAssessment(
        state=state,
        evidence_status=evidence,
        confidence="low" if state == "S1" else ("high" if state == "S4" else "moderate"),
        confidence_reason=(
            "severity, duration and associated symptoms unknown"
            if state == "S1"
            else ("current high-acuity pattern from reported findings" if state == "S4" else "pattern characterized from reported findings")
        ),
        override=state == "S4",
        discovery_can_continue=state in {"S0", "S1", "S2"},
        clinical_followup_needed=state in {"S2", "S3", "S4"},
        urgency={"S0": "none", "S1": "none", "S2": "routine", "S3": "prompt", "S4": "emergency"}[state],
        domain=domain,
        missing=unknown,
        known=known,
        clarifiers=clarifiers,
        findings=findings,
        interpretations=interpretations,
        safety_net={
            "domain": domain,
            "current_state": "interrupt" if state == "S4" else ("limited" if state == "S3" else "continue_discovery"),
            "watch_for": list(_WATCH.get(domain, _WATCH["general"])),
            "review_trigger": "new_or_worsening_symptoms",
        },
        recommended_action={"S4": "emergency", "S3": "prompt_evaluation", "S1": "clarify", "S2": "continue", "S0": "continue"}[state],
        message=_message(state, domain),
        preface=_preface(domain, state),
    )
    assessment = critique(assessment)
    if assessment.state == "S1" and not assessment.clarifiers:
        assessment.clarifiers = [item for item in _clarifiers(assessment.domain, assessment.missing) if item.code not in asked]
    assessment.message = _sanitize(_message(assessment.state, assessment.domain) or assessment.message)
    assessment.preface = _sanitize(assessment.preface)
    return assessment


def _sanitize(text: str) -> str:
    lowered = (text or "").lower()
    if any(phrase in lowered for phrase in _BANNED_COPY):
        return "I updated the safety review from the reported findings. This is not a diagnosis."
    return text or ""


def screen_safety(text: str) -> SafetyAssessment:
    """Every turn. Findings only. Not a diagnosis."""
    return assess_safety(extract_safety_findings(text))


SAFETY_ENGINE_RULE = (
    "You are not determining whether the patient has a dangerous diagnosis. "
    "You are determining whether the factual presentation supplied contains enough evidence "
    "to warrant interrupting normal Discovery for higher-acuity medical evaluation. "
    "Do not escalate based solely on a disease name, patient interpretation, inferred mechanism, "
    "hypothetical diagnosis, or knowledge that a symptom can sometimes be associated with serious disease. "
    "When essential acuity information is missing, request the smallest number of safety-discriminating "
    "facts necessary before escalating, unless the existing information already clearly meets an urgent threshold. "
    "Distinguish chronic, stable, recurrent, progressive, acute and acute-on-chronic presentations. "
    "Respect explicit negatives and temporality."
)
