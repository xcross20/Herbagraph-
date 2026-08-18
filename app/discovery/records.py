"""Classify uploaded *reports*. Labs stay on the existing upload parser."""

from __future__ import annotations

import re

from app.discovery.intake import ExtractedFact


def _readable_payload(text: str) -> str:
    stripped = re.sub(r"%pdf[-\d.]*", " ", text or "", flags=re.I)
    stripped = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", stripped)
    return " ".join(stripped.split())


def _is_unreadable_upload(filename: str, text: str) -> bool:
    name = (filename or "").lower()
    lower = (text or "").lower()
    if "unreadable" in lower or "binary junk" in lower:
        return True
    readable = _readable_payload(text)
    if name.endswith((".png", ".jpg")) and len(readable) < 20:
        return True
    if name.endswith(".pdf") and len(readable) < 40:
        return True
    return False


def classify_document(filename: str, text: str) -> str:
    from app.discovery.tripwires import record_document_classified

    name = (filename or "").lower()
    blob = (text or "").lower()
    if "unreadable" in blob or "binary junk" in blob:
        record_document_classified("unsupported")
        return "unsupported"
    if name.endswith(".csv") or "reference range" in blob or "labcorp" in blob or "quest diagnostics" in blob:
        record_document_classified("lab")
        return "lab"
    if "emg" in name or "nerve conduction" in blob or re.search(r"\bncs\b", blob) or "needle emg" in blob:
        record_document_classified("emg")
        return "emg"
    if "mri" in name or "ct " in blob or "radiology" in blob or "impression:" in blob:
        record_document_classified("radiology")
        return "radiology"
    if _is_unreadable_upload(filename, text):
        record_document_classified("unsupported")
        return "unsupported"
    if len(_readable_payload(text)) < 20:
        record_document_classified("unknown")
        return "unknown"
    record_document_classified("note")
    return "note"


def extract_record_findings(kind: str, text: str) -> list[ExtractedFact]:
    blob = (text or "").lower()
    if kind == "emg":
        value = "reported_normal" if "normal" in blob and "abnormal" not in blob else "mentioned"
        return [
            ExtractedFact(name="emg testing", value=value, kind="assessment"),
            ExtractedFact(name="emg_report", value="attached", kind="assessment"),
        ]
    if kind == "radiology":
        excerpt = " ".join((text or "").split())[:240]
        return [ExtractedFact(name="radiology report", value=excerpt or "uploaded", kind="context")]
    if kind == "note":
        excerpt = " ".join((text or "").split())[:240]
        return [ExtractedFact(name="clinical note", value=excerpt or "uploaded", kind="context")]
    return []
