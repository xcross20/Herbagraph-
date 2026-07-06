"""Stage 1: Lab Parser.

Accepts a PDF (via pdfplumber, falling back to pytesseract OCR for scanned
pages) or plain text lab report and extracts raw (test_name, value, unit,
reference_range) rows using four layered regex patterns, covering Quest,
LabCorp, and generic tabular/CSV/pipe-delimited formats.
"""

import io
import re

from app.schemas.pipeline import ParsedLabResult

_NUM = r"[<>]?\s*-?\d+\.?\d*"

# Pattern 1: "Test Name    123.4  mg/dL   (0.0-3.0)"  -- Quest-style with parenthesized range
_PATTERN_PAREN_RANGE = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,45}}?)\s{{2,}}"
    rf"(?P<value>{_NUM})\s*"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s*"
    rf"\(\s*(?P<low>{_NUM})\s*[-–to]+\s*(?P<high>{_NUM})\s*\)\s*$"
)

# Pattern 2: "Test Name  123.4 mg/dL  H  70-99"  -- LabCorp-style, optional flag, dash range (no parens)
_PATTERN_PLAIN_RANGE = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,45}}?)\s{{2,}}"
    rf"(?P<value>{_NUM})\s*"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s*"
    rf"(?:[HL*]\s+)?"
    rf"(?P<low>{_NUM})\s*[-–]\s*(?P<high>{_NUM})\s*$"
)

# Pattern 3: pipe-delimited table "Test Name | 123.4 | mg/dL | 70-99"
_PATTERN_PIPE = re.compile(
    rf"^(?P<name>[^|]+?)\s*\|\s*(?P<value>{_NUM})\s*\|\s*"
    rf"(?P<unit>[^|]*?)\s*\|\s*(?P<low>{_NUM})\s*[-–]\s*(?P<high>{_NUM})\s*$"
)

# Pattern 4: CSV "Test Name,123.4,mg/dL,70,99"
_PATTERN_CSV = re.compile(
    rf"^(?P<name>[^,]+?)\s*,\s*(?P<value>{_NUM})\s*,\s*"
    rf"(?P<unit>[^,]*?)\s*,\s*(?P<low>{_NUM})\s*,\s*(?P<high>{_NUM})\s*$"
)

_PATTERNS = (_PATTERN_PAREN_RANGE, _PATTERN_PLAIN_RANGE, _PATTERN_PIPE, _PATTERN_CSV)


def _to_float(raw: str) -> float:
    return float(raw.strip().lstrip("<>").strip())


def parse_lab_line(line: str) -> ParsedLabResult | None:
    """Attempt to parse a single line of lab report text against the four layered patterns."""
    stripped = line.strip()
    if not stripped:
        return None

    for pattern in _PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        groups = match.groupdict()
        try:
            value = _to_float(groups["value"])
            low = _to_float(groups["low"])
            high = _to_float(groups["high"])
        except ValueError:
            continue
        name = groups["name"].strip().rstrip(":").strip()
        if not name:
            continue
        unit = (groups.get("unit") or "").strip() or None
        return ParsedLabResult(
            raw_test_name=name,
            value=value,
            unit=unit,
            reference_range_low=low,
            reference_range_high=high,
            raw_line=stripped,
        )
    return None


def parse_lab_text(text: str) -> list[ParsedLabResult]:
    """Parse a full lab report's plain text into a list of ParsedLabResult rows."""
    results: list[ParsedLabResult] = []
    for line in text.splitlines():
        parsed = parse_lab_line(line)
        if parsed is not None:
            results.append(parsed)
    return results


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF, falling back to OCR for scanned/image-only pages."""
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
            else:
                text_parts.append(_ocr_page(page))
    return "\n".join(text_parts)


def _ocr_page(page) -> str:
    import pytesseract

    image = page.to_image(resolution=300).original
    return pytesseract.image_to_string(image)


def parse_lab_file(file_bytes: bytes, filename: str) -> list[ParsedLabResult]:
    """Dispatch on file extension: OCR/extract PDFs, decode everything else as text."""
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="replace")
    return parse_lab_text(text)
