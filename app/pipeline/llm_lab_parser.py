"""LLM-assisted lab report parsing when regex patterns fail.

Stage 1 fallback: after pdfplumber/pytesseract text extraction, if no rows match
the deterministic parser, send de-identified text (or page images) to the LLM and
map the structured response into ParsedLabResult rows.
"""

from __future__ import annotations

import base64
import io
import json
import logging

from app.config import get_settings
from app.pipeline.llm_client import create_sync_client, llm_configured, sync_chat_json_with_fallback
from app.core.privacy import deidentify_text
from app.schemas.pipeline import ParsedLabResult

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 48_000
_MAX_VISION_PAGES = 6
_VISION_DPI = 200

_SYSTEM_PROMPT = """You extract structured biomarker rows from clinical lab reports.

Return a single JSON object:
{
  "results": [
    {
      "raw_test_name": "string — test name exactly as shown on the report",
      "value": number,
      "unit": "string or null",
      "reference_range_low": number or null,
      "reference_range_high": number or null,
      "qualitative_result": "string or null — for DETECTED/POSITIVE/NEGATIVE etc.",
      "expected_result": "string or null — reference expectation for qualitative tests"
    }
  ]
}

Rules:
1. Extract every measurable lab test you can find (chemistry, CBC, lipids, hormones, urinalysis, etc.).
2. For numeric tests, parse value and reference range when present.
3. For qualitative tests (e.g. H. pylori DETECTED, culture results), set value to 1.0 if abnormal/positive \
   and 0.0 if normal/negative; put the qualitative wording in unit or qualitative_result.
4. Do not invent tests that are not on the report. Skip panel headers, billing lines, and addresses.
5. If reference range uses > or < only, set the bound you have and null the other.
6. Return {"results": []} only if the document truly contains no lab measurements.
"""


class LLMLabParserError(Exception):
    pass


def _client():
    if not llm_configured():
        raise LLMLabParserError("LLM API key is not configured (OPENAI_API_KEY or MINIMAX_API_KEY)")
    return create_sync_client()


def _vision_model() -> str:
    cfg = get_settings()
    return cfg.llm_vision_model or cfg.llm_model


def _rows_from_llm_payload(data: dict) -> list[ParsedLabResult]:
    rows: list[ParsedLabResult] = []
    for raw in data.get("results", []):
        if not isinstance(raw, dict):
            continue
        name = (raw.get("raw_test_name") or "").strip()
        if not name:
            continue
        try:
            value = float(raw.get("value", 0))
        except (TypeError, ValueError):
            continue

        low = raw.get("reference_range_low")
        high = raw.get("reference_range_high")
        try:
            low_f = float(low) if low is not None else None
        except (TypeError, ValueError):
            low_f = None
        try:
            high_f = float(high) if high is not None else None
        except (TypeError, ValueError):
            high_f = None

        unit = raw.get("unit")
        unit_str = str(unit).strip() if unit not in (None, "") else None

        qual = raw.get("qualitative_result")
        qual_str = str(qual).strip().upper() if qual not in (None, "") else None
        expected = raw.get("expected_result")
        expected_str = str(expected).strip().upper() if expected not in (None, "") else None

        rows.append(
            ParsedLabResult(
                raw_test_name=name,
                value=value,
                unit=unit_str,
                reference_range_low=low_f if low_f is not None else 0.0,
                reference_range_high=high_f if high_f is not None else 0.0,
                raw_line=f"llm:{name}",
                qualitative_result=qual_str,
                expected_result=expected_str,
            )
        )
    return rows


def parse_llm_response(raw_text: str) -> list[ParsedLabResult]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMLabParserError(f"LLM did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMLabParserError("LLM response was not a JSON object")
    return _rows_from_llm_payload(data)


def parse_lab_text_with_llm(text: str) -> list[ParsedLabResult]:
    """Extract biomarker rows from plain text using the configured LLM."""
    cleaned = deidentify_text(text.strip())
    if not cleaned:
        return []

    payload = cleaned[:_MAX_TEXT_CHARS]
    raw, fallback_provider = sync_chat_json_with_fallback(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract biomarker rows from this lab report text:\n\n{payload}"},
        ],
    )
    if fallback_provider:
        logger.info("Lab text parse used fallback LLM provider: %s", fallback_provider)
    rows = parse_llm_response(raw)
    logger.info("LLM text parser extracted %d rows", len(rows))
    return rows


def _pdf_page_images(file_bytes: bytes, max_pages: int = _MAX_VISION_PAGES) -> list[bytes]:
    import pdfplumber

    images: list[bytes] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            pil_image = page.to_image(resolution=_VISION_DPI).original
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            images.append(buf.getvalue())
    return images


def parse_lab_pdf_with_vision(file_bytes: bytes) -> list[ParsedLabResult]:
    """Vision fallback for scanned or layout-heavy PDFs when text parsing fails."""
    images = _pdf_page_images(file_bytes)
    if not images:
        return []

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "This is a clinical lab report PDF rendered as page images. "
                "Extract every biomarker/test row you can read."
            ),
        }
    ]
    for image_bytes in images:
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    _client()  # validate API key before vision request
    raw, fallback_provider = sync_chat_json_with_fallback(
        model=_vision_model(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    if fallback_provider:
        logger.info("Lab vision parse used fallback LLM provider: %s", fallback_provider)
    rows = parse_llm_response(raw)
    logger.info("LLM vision parser extracted %d rows from %d pages", len(rows), len(images))
    return rows