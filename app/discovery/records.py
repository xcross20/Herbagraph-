"""Classify uploaded *reports*. Labs stay on the existing upload parser."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.discovery.intake import ExtractedFact
from app.discovery.resolver import resolve_test
from app.models.enums import ResolverStatus

DOCUMENT_OUTCOMES = (
    "accepted",
    "partial",
    "unsupported",
    "failed",
    "needs_ocr",
    "ambiguous",
    "routed_to_lab_engine",
)


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


@dataclass(frozen=True)
class DocumentClassification:
    kind: str
    outcome: str
    checksum: str
    classification_confidence: float
    extraction_confidence: float
    parser_version: str = "document-classifier-v2"


def document_checksum(filename: str, text: str) -> str:
    payload = f"{filename}\n{text or ""}".encode()
    return hashlib.sha256(payload).hexdigest()


def classify_document_outcome(filename: str, text: str) -> DocumentClassification:
    from app.discovery.tripwires import record_document_classified

    name = (filename or "").lower()
    blob = (text or "").lower()
    checksum = document_checksum(filename, text)
    readable = _readable_payload(text)
    if "encrypt" in blob or "corrupt" in blob:
        record_document_classified("failed")
        return DocumentClassification("unsupported", "failed", checksum, 0.9, 0.0)
    if "scanned image" in blob or "ocr required" in blob:
        record_document_classified("needs_ocr")
        return DocumentClassification("unknown", "needs_ocr", checksum, 0.8, 0.0)
    if "unreadable" in blob or "binary junk" in blob:
        record_document_classified("unsupported")
        return DocumentClassification("unsupported", "unsupported", checksum, 0.95, 0.0)
    if name.endswith(".csv") or "reference range" in blob or "labcorp" in blob or "quest diagnostics" in blob:
        record_document_classified("lab")
        return DocumentClassification("lab", "routed_to_lab_engine", checksum, 0.95, 0.0)
    if re.search(r"\bmri\b", blob) or name.endswith("mri.txt") or " mri" in f" {name}":
        resolved = resolve_test("MRI")
        if resolved.status is ResolverStatus.AMBIGUOUS or not re.search(
            r"brain|cervical|lumbar|spine|head|knee|shoulder", blob + " " + name
        ):
            record_document_classified("ambiguous")
            return DocumentClassification("radiology", "ambiguous", checksum, 0.7, 0.2)
    if "emg" in name or "nerve conduction" in blob or re.search(r"\bncs\b", blob) or "needle emg" in blob:
        record_document_classified("emg")
        return DocumentClassification("emg", "accepted", checksum, 0.9, 0.85)
    if "mri" in name or "ct " in blob or "radiology" in blob or "impression:" in blob:
        record_document_classified("radiology")
        return DocumentClassification("radiology", "partial", checksum, 0.8, 0.4)
    if _is_unreadable_upload(filename, text):
        record_document_classified("unsupported")
        return DocumentClassification("unsupported", "failed", checksum, 0.9, 0.0)
    if len(readable) < 20:
        record_document_classified("unknown")
        return DocumentClassification("unknown", "failed", checksum, 0.4, 0.0)
    record_document_classified("note")
    return DocumentClassification("note", "accepted", checksum, 0.75, 0.5)


def classify_document(filename: str, text: str) -> str:
    return classify_document_outcome(filename, text).kind


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
