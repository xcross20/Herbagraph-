"""Classify uploaded *reports*. Labs stay on the existing upload parser."""

from __future__ import annotations

import re

from app.discovery.intake import ExtractedFact


def classify_document(filename: str, text: str) -> str:
    from app.discovery.tripwires import record_document_classified

    name = (filename or "").lower()
    blob = (text or "").lower()
    if name.endswith((".pdf", ".png", ".jpg")) and (
        "%pdf" in blob or "unreadable" in blob or "binary junk" in blob
    ):
        record_document_classified("unsupported")
        return "unsupported"
    if name.endswith(".csv") or "reference range" in blob or "labcorp" in blob or "quest diagnostics" in blob:
        record_document_classified("lab")
        return "lab"
    if "emg" in name or "nerve conduction" in blob or re.search(r"\bncs\b", blob) or "needle emg" in blob:
        record_document_classified("emg")
        return "emg"
    if "mri" in name or "ct " in blob or "radiology" in blob or "impression:" in blob:
        return "radiology"
    if len(blob.strip()) < 20:
        return "unknown"
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
