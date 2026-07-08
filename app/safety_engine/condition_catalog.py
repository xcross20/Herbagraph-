"""Clinical condition categories for contraindication and caution matching."""

from __future__ import annotations

import re

CONDITION_CATALOG: dict[str, dict] = {
    "pregnancy": {
        "patterns": [r"\bpregnan", r"\bgestation", r"\btrimester"],
        "label": "Pregnancy",
    },
    "breastfeeding": {
        "patterns": [r"\blactat", r"\bbreast\s*feed", r"\bnursing\b"],
        "label": "Breastfeeding",
    },
    "liver_disease": {
        "patterns": [r"\bliver\s+disease", r"\bhepatitis", r"\bcirrhosis", r"\bnafld", r"\bfatty\s+liver", r"\bhepatic"],
        "label": "Liver disease",
    },
    "kidney_disease": {
        "patterns": [r"\bckd\b", r"\bkidney\s+disease", r"\brenal\s+failure", r"\bchronic\s+kidney"],
        "label": "Kidney disease",
    },
    "bleeding_disorder": {
        "patterns": [r"\bbleeding\s+disorder", r"\bhemophilia", r"\banticoagulant", r"\bcoagulopathy"],
        "label": "Bleeding disorder",
    },
    "autoimmune_disease": {
        "patterns": [r"\blupus", r"\brheumatoid", r"\bautoimmune", r"\bcrohn", r"\bhashimoto", r"\bmultiple\s+sclerosis"],
        "label": "Autoimmune disease",
    },
    "organ_transplant": {
        "patterns": [r"\btransplant", r"\borgan\s+recipient"],
        "label": "Organ transplant",
    },
    "diabetes": {
        "patterns": [r"\bdiabetes", r"\bdiabetic", r"\btype\s*1\s*diabetes", r"\btype\s*2\s*diabetes"],
        "label": "Diabetes",
    },
    "hypertension": {
        "patterns": [r"\bhypertension", r"\bhigh\s+blood\s+pressure"],
        "label": "Hypertension",
    },
    "thyroid_disease": {
        "patterns": [r"\bhyperthyroid", r"\bhypothyroid", r"\bgraves", r"\bthyroid\s+disease"],
        "label": "Thyroid disease",
    },
}


def active_conditions(known_conditions: list[str]) -> set[str]:
    blob = " ".join(known_conditions or []).lower()
    active: set[str] = set()
    for key, meta in CONDITION_CATALOG.items():
        for pattern in meta["patterns"]:
            if re.search(pattern, blob, re.IGNORECASE):
                active.add(key)
                break
    return active