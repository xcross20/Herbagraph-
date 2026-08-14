import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_MRN_RE = re.compile(r"\b(?:MRN|Patient ID|Acct(?:ount)?\s*#?)\s*[:#]?\s*[A-Za-z0-9-]{4,}\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
_NAME_LABEL_RE = re.compile(
    r"\b(?:Patient|Name|Client|Member)\s*[:\-]\s*[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,3}",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'\s]{2,40}\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way)\b\.?",
    re.IGNORECASE,
)

_REDACTION = "[REDACTED]"


def deidentify_text(text: str) -> str:
    """Strip HIPAA Safe Harbor direct identifiers from free text before it leaves the system."""
    if not text:
        return text

    redacted = text
    for pattern in (
        _NAME_LABEL_RE,
        _EMAIL_RE,
        _SSN_RE,
        _PHONE_RE,
        _MRN_RE,
        _ADDRESS_RE,
        _DATE_RE,
        _ZIP_RE,
    ):
        redacted = pattern.sub(_REDACTION, redacted)
    return redacted


def deidentify_payload(payload: dict) -> dict:
    """Recursively de-identify string values within a dict/list payload sent to the LLM."""
    if not settings.deidentify_before_llm:
        return payload
    return _deidentify_value(payload)


def _deidentify_value(value):
    if isinstance(value, str):
        return deidentify_text(value)
    if isinstance(value, dict):
        return {k: _deidentify_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deidentify_value(v) for v in value]
    return value


class EncryptionError(Exception):
    pass


def encryption_key_fingerprint() -> str | None:
    """Short hash so web vs worker keys can be compared without leaking the key."""
    key = (settings.encryption_key or "").strip()
    if not key:
        return None
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _get_fernet() -> Fernet:
    if not settings.encryption_key:
        raise EncryptionError("ENCRYPTION_KEY is not configured")
    return Fernet(settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key)


def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _get_fernet().decrypt(token)
    except InvalidToken as exc:
        raise EncryptionError("Failed to decrypt data: invalid token or key") from exc


def encrypt_str(data: str) -> str:
    return encrypt_bytes(data.encode("utf-8")).decode("utf-8")


def decrypt_str(token: str) -> str:
    return decrypt_bytes(token.encode("utf-8")).decode("utf-8")
