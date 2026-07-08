"""Stage 1: Lab Parser.

Accepts a PDF (via pdfplumber, falling back to pytesseract OCR for scanned
pages) or plain text lab report and extracts raw (test_name, value, unit,
reference_range) rows using four layered regex patterns, covering Quest,
LabCorp, and generic tabular/CSV/pipe-delimited formats.
"""

import io
import re

from app.pipeline.user_biomarker_profile import clean_parsed_test_name
from app.schemas.pipeline import ParsedLabResult


def _parsed_test_name(raw: str | list | None) -> str:
    if isinstance(raw, list):
        raw = " ".join(str(part) for part in raw if part is not None)
    return clean_parsed_test_name(str(raw).strip().rstrip(":").strip())

_NUM = r"[<>]?\s*-?\d+\.?\d*"
# Quest/LabCorp analyte names may start with % (e.g. "% Saturation").
_NAME_START = r"[%A-Za-z]"

# Pattern 1: "Test Name    123.4  mg/dL   (0.0-3.0)"  -- Quest-style with parenthesized range
_PATTERN_PAREN_RANGE = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,45}}?)\s{{2,}}"
    rf"(?P<value>{_NUM})\s*"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s*"
    rf"\(\s*(?P<low>{_NUM})\s*[-–to]+\s*(?P<high>{_NUM})\s*\)\s*$"
)

# Pattern 2: "Test Name  123.4 mg/dL  H  70-99"  -- LabCorp-style, optional flag, dash range (no parens)
_PATTERN_PLAIN_RANGE = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,45}}?)\s{{2,}}"
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

# Pattern 5: Quest PDF export "GLUCOSE 76 Reference Range: 65-99 mg/dL"
_PATTERN_QUEST_REF = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,60}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"Reference Range:\s*(?P<range>.+?)\s*$",
    re.IGNORECASE,
)

# Pattern 6: Quest qualitative microbiology/serology
# e.g. "HELICOBACTER PYLORI, UREA BREATH TEST DETECTED Reference Range: NOT DETECTED"
_QUALITATIVE_RESULTS = (
    r"NOT\s+DETECTED|NON-REACTIVE|NEGATIVE|ABSENT|NORMAL|"
    r"DETECTED|REACTIVE|POSITIVE|PRESENT|ABNORMAL"
)
_PATTERN_QUEST_QUALITATIVE = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,80}}?)\s+"
    rf"(?P<result>{_QUALITATIVE_RESULTS})\s+"
    rf"Reference Range:\s*(?P<expected>.+?)\s*$",
    re.IGNORECASE,
)

_POSITIVE_QUALITATIVE = frozenset({"detected", "reactive", "positive", "present", "abnormal"})
_NEGATIVE_QUALITATIVE = frozenset({"not detected", "non-reactive", "negative", "absent", "normal"})
_NO_GROWTH = frozenset({"no growth", "not isolated", "none isolated", "sterile", "negative"})

# Pattern 7: culture lines — "URINE CULTURE    Escherichia coli" or "STOOL CULTURE    No growth"
_PATTERN_CULTURE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{1,50}?)\s{2,}"
    r"(?P<result>[A-Za-z][A-Za-z0-9/(),.'%\- ]{1,80}?)\s*$",
    re.IGNORECASE,
)

# Pattern 8: PGx genotype — "CYP2D6    *1/*2    Normal Metabolizer"
_PATTERN_PGX = re.compile(
    r"^(?P<name>CYP2[A-Z0-9]+|VKORC1|SLCO1B1|TPMT|DPYD|HLA[\-\*A-Z0-9]+|MTHFR|Factor\s+V\s+Leiden|Prothrombin)\s+"
    r"(?:(?P<genotype>[*][0-9A-Za-z/]+(?:\s*[/]\s*[*]?[0-9A-Za-z/]+)?)\s+)?"
    r"(?P<phenotype>[A-Za-z][A-Za-z0-9/(),.'%\- ]{0,60}?)\s*$",
    re.IGNORECASE,
)

_RANGE_DASH = re.compile(
    rf"^(?P<low>{_NUM})\s*[-–]\s*(?P<high>{_NUM})\s*(?P<unit>.*)$",
    re.IGNORECASE,
)
_RANGE_GT = re.compile(rf"^>\s*(?:=?\s*)?(?P<low>{_NUM})\s*(?P<unit>.*)$", re.IGNORECASE)
_RANGE_LT = re.compile(rf"^<\s*(?:=?\s*)?(?P<high>{_NUM})\s*(?P<unit>.*)$", re.IGNORECASE)

_STATUS_TOKEN = r"(?:NEAR\s+OPTIMAL|BORDERLINE\s+HIGH|BORDERLINE\s+LOW|OPTIMAL|[HL*]|HIGH|LOW)"

# Pattern 9: "HDL 52.0 L 60.00 - 180.00 (mg/dL)" — compact name, flag, range, unit in parens
_PATTERN_FLAG_RANGE_UNIT = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?:(?P<flag>{_STATUS_TOKEN})\s+)?"
    rf"(?P<low>{_NUM})\s*[-–]\s*(?P<high>{_NUM})\s*"
    rf"\(\s*(?P<unit>[^)]+)\s*\)\s*$",
    re.IGNORECASE,
)

# Pattern 10a: "F Triglycerides 63.0 <= 150.00 (mg/dL)" — upper-bound-only with <=
_PATTERN_FLAG_LTE_RANGE_UNIT = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?:(?P<flag>{_STATUS_TOKEN})\s+)?"
    rf"<=\s*(?P<high>{_NUM})\s*"
    rf"\(\s*(?P<unit>[^)]+)\s*\)\s*$",
    re.IGNORECASE,
)

# Pattern 10b: "F HbA1c 5.9 H < 5.70 (%)" — Healow/Quest upper-bound-only with < (not <=)
_PATTERN_FLAG_LT_RANGE_UNIT = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?:(?P<flag>{_STATUS_TOKEN})\s+)?"
    rf"<\s*(?P<high>{_NUM})\s*"
    rf"\(\s*(?P<unit>[^)]+)\s*\)\s*$",
    re.IGNORECASE,
)

# Pattern 10c: "F Estimated Average Glucose 122.63 (mg/dL)" — value + unit, no reference range
_PATTERN_VALUE_UNIT_PARENS = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,60}}?)\s+"
    rf"(?P<value>{_NUM})\s*"
    rf"\(\s*(?P<unit>[^)]+)\s*\)\s*$",
    re.IGNORECASE,
)

# Pattern 10: "LDL Cholesterol Calc 109.4 NEAR OPTIMAL 0.00 - 100.00"
_PATTERN_VALUE_STATUS_RANGE = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9/(),.'%\- ]{{1,60}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?:(?P<flag>{_STATUS_TOKEN})\s+)?"
    rf"(?P<low>{_NUM})\s*[-–]\s*(?P<high>{_NUM})\s*"
    rf"(?:(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s*)?$",
    re.IGNORECASE,
)

# Pattern 11: "Glucose 102 mg/dL 65-99" — standard row (name value unit range)
_PATTERN_STANDARD_ROW = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)\s+"
    rf"(?P<low>{_NUM})\s*[-–—to]+\s*(?P<high>{_NUM})\s*$",
    re.IGNORECASE,
)

# Pattern 12: "Ferritin 12 L ng/mL 38-380" — flagged row with trailing range
_PATTERN_FLAGGED_ROW = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?:(?P<flag>{_STATUS_TOKEN})\s+)?"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)\s+"
    rf"(?P<low>{_NUM})\s*[-–—to]+\s*(?P<high>{_NUM})\s*$",
    re.IGNORECASE,
)

# Pattern 13: inline reference text — "Vitamin D 25 ng/mL Reference Range: 30-100"
_PATTERN_INLINE_REF_TEXT = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,60}}?)\s+"
    rf"(?P<value>{_NUM})\s*"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s+"
    rf"(?:Reference Range|Ref Range|Normal Range|Range)\s*:\s*"
    rf"(?P<low>{_NUM})\s*[-–—to]+\s*(?P<high>{_NUM})",
    re.IGNORECASE,
)

# Pattern 14: percent row — "Neutrophils 58 % 40-70"
_PATTERN_PERCENT_ROW = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<value>{_NUM})\s*%\s+"
    rf"(?P<low>{_NUM})\s*[-–—to]+\s*(?P<high>{_NUM})\s*%?\s*$",
    re.IGNORECASE,
)

# Pattern 15: bounded only — "hs-CRP >10.0 mg/L" or "<5 ng/mL"
_PATTERN_BOUNDED_VALUE = re.compile(
    rf"^(?P<name>{_NAME_START}[A-Za-z0-9/(),.'%\- ]{{1,50}}?)\s+"
    rf"(?P<bounded>[<>]=?\s*{_NUM})\s*"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s*$",
    re.IGNORECASE,
)

_PATTERNS = (_PATTERN_PAREN_RANGE, _PATTERN_PLAIN_RANGE, _PATTERN_PIPE, _PATTERN_CSV)


def _to_float(raw: str) -> float:
    return float(raw.strip().lstrip("<>").strip())


def _clean_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    unit = raw.strip()
    unit = re.sub(r"\s*\(calc\)\s*$", "", unit, flags=re.IGNORECASE)
    unit = re.sub(r"\s*calc\s*$", "", unit, flags=re.IGNORECASE)
    unit = unit.strip()
    return unit or None


def _parse_quest_reference_range(range_part: str) -> tuple[float | None, float | None, str | None] | None:
    """Parse Quest 'Reference Range:' tail into (low, high, unit)."""
    cleaned = range_part.strip()
    if not cleaned or cleaned.upper() in {"NEGATIVE", "NON-REACTIVE", "REACTIVE", "CLEAR", "YELLOW", "NONE SEEN"}:
        return None

    for pattern, parser in (
        (_RANGE_DASH, lambda m: (m.group("low"), m.group("high"), m.group("unit"))),
        (_RANGE_GT, lambda m: (m.group("low"), None, m.group("unit"))),
        (_RANGE_LT, lambda m: (None, m.group("high"), m.group("unit"))),
    ):
        match = pattern.match(cleaned)
        if not match:
            continue
        low_raw, high_raw, unit_raw = parser(match)
        try:
            low = _to_float(low_raw) if low_raw is not None else 0.0
            high = _to_float(high_raw) if high_raw is not None else low * 10 if low > 0 else 9999.0
        except ValueError:
            continue
        return low, high, _clean_unit(unit_raw)

    return None


def _normalize_qualitative_label(raw: str) -> str:
    collapsed = re.sub(r"\s+", " ", raw.strip().upper())
    return collapsed


def _qualitative_value(result_label: str) -> float:
    """Encode qualitative results as 0 (expected/negative) or 1 (positive/abnormal)."""
    normalized = _normalize_qualitative_label(result_label).lower()
    if normalized in _POSITIVE_QUALITATIVE:
        return 1.0
    if normalized in _NEGATIVE_QUALITATIVE:
        return 0.0
    # Conservative default: unknown qualitative wording treated as non-actionable.
    return 0.0


def _parse_culture_line(line: str) -> ParsedLabResult | None:
    stripped = line.strip()
    if "culture" not in stripped.lower():
        return None
    match = _PATTERN_CULTURE.match(stripped)
    if not match:
        return None
    name = _parsed_test_name(match.group("name"))
    result = match.group("result").strip()
    if not name or not result:
        return None
    result_lower = result.lower()
    is_growth = not any(neg in result_lower for neg in _NO_GROWTH)
    return ParsedLabResult(
        raw_test_name=name,
        value=1.0 if is_growth else 0.0,
        unit=result if is_growth else "NO GROWTH",
        reference_range_low=0.0,
        reference_range_high=0.0,
        raw_line=stripped,
        qualitative_result=result.upper() if is_growth else "NO GROWTH",
        expected_result="NO GROWTH",
    )


def _parse_pgx_line(line: str) -> ParsedLabResult | None:
    match = _PATTERN_PGX.match(line.strip())
    if not match:
        return None
    name = match.group("name").strip()
    genotype = (match.group("genotype") or "").strip()
    phenotype = (match.group("phenotype") or "").strip()
    label_parts = [p for p in (genotype, phenotype) if p]
    label = " ".join(label_parts) if label_parts else phenotype or genotype
    if not label:
        return None
    phenotype_lower = phenotype.lower()
    actionable = any(
        token in phenotype_lower
        for token in ("poor", "intermediate", "ultrarapid", "rapid", "positive", "carrier", "homozygous", "heterozygous")
    )
    canonical_suffix = " Genotype" if "genotype" not in name.lower() else ""
    return ParsedLabResult(
        raw_test_name=_parsed_test_name(f"{name}{canonical_suffix}"),
        value=1.0 if actionable else 0.0,
        unit=label,
        reference_range_low=0.0,
        reference_range_high=0.0,
        raw_line=line.strip(),
        qualitative_result=label.upper(),
        expected_result="NORMAL METABOLIZER",
    )


def _parse_quest_qualitative_line(line: str) -> ParsedLabResult | None:
    match = _PATTERN_QUEST_QUALITATIVE.match(line.strip())
    if not match:
        return None
    groups = match.groupdict()
    name = _parsed_test_name(groups["name"])
    if not name:
        return None
    result_label = _normalize_qualitative_label(groups["result"])
    expected_label = _normalize_qualitative_label(groups["expected"])
    return ParsedLabResult(
        raw_test_name=name,
        value=_qualitative_value(result_label),
        unit=result_label,
        reference_range_low=0.0,
        reference_range_high=0.0,
        raw_line=line.strip(),
        qualitative_result=result_label,
        expected_result=expected_label,
    )


def _parse_flag_range_line(line: str) -> ParsedLabResult | None:
    lt_match = _PATTERN_FLAG_LT_RANGE_UNIT.match(line.strip())
    if lt_match:
        groups = lt_match.groupdict()
        try:
            value = _to_float(groups["value"])
            high = _to_float(groups["high"])
        except ValueError:
            return None
        name = _parsed_test_name(groups["name"])
        if not name:
            return None
        unit = _clean_unit(groups.get("unit"))
        return ParsedLabResult(
            raw_test_name=name,
            value=value,
            unit=unit,
            reference_range_low=0.0,
            reference_range_high=high,
            raw_line=line.strip(),
        )

    lte_match = _PATTERN_FLAG_LTE_RANGE_UNIT.match(line.strip())
    if lte_match:
        groups = lte_match.groupdict()
        try:
            value = _to_float(groups["value"])
            high = _to_float(groups["high"])
        except ValueError:
            return None
        name = _parsed_test_name(groups["name"])
        if not name:
            return None
        unit = _clean_unit(groups.get("unit"))
        return ParsedLabResult(
            raw_test_name=name,
            value=value,
            unit=unit,
            reference_range_low=0.0,
            reference_range_high=high,
            raw_line=line.strip(),
        )

    for pattern in (_PATTERN_FLAG_RANGE_UNIT, _PATTERN_VALUE_STATUS_RANGE):
        match = pattern.match(line.strip())
        if not match:
            continue
        groups = match.groupdict()
        try:
            value = _to_float(groups["value"])
            low = _to_float(groups["low"])
            high = _to_float(groups["high"])
        except ValueError:
            continue
        name = _parsed_test_name(groups["name"])
        if not name:
            continue
        unit = _clean_unit(groups.get("unit"))
        return ParsedLabResult(
            raw_test_name=name,
            value=value,
            unit=unit,
            reference_range_low=low,
            reference_range_high=high,
            raw_line=line.strip(),
        )
    return None


def _parse_quest_ref_line(line: str) -> ParsedLabResult | None:
    match = _PATTERN_QUEST_REF.match(line.strip())
    if not match:
        return None
    groups = match.groupdict()
    try:
        value = _to_float(groups["value"])
    except ValueError:
        return None
    parsed_range = _parse_quest_reference_range(groups["range"])
    if parsed_range is None:
        return None
    low, high, unit = parsed_range
    name = _parsed_test_name(groups["name"])
    if not name:
        return None
    return ParsedLabResult(
        raw_test_name=name,
        value=value,
        unit=unit,
        reference_range_low=low,
        reference_range_high=high,
        raw_line=line.strip(),
    )


def parse_lab_line(line: str) -> ParsedLabResult | None:
    """Attempt to parse a single line of lab report text against the four layered patterns."""
    stripped = line.strip()
    if not stripped:
        return None

    qualitative = _parse_quest_qualitative_line(stripped)
    if qualitative is not None:
        return qualitative

    culture = _parse_culture_line(stripped)
    if culture is not None:
        return culture

    pgx = _parse_pgx_line(stripped)
    if pgx is not None:
        return pgx

    quest = _parse_quest_ref_line(stripped)
    if quest is not None:
        return quest

    flag_range = _parse_flag_range_line(stripped)
    if flag_range is not None:
        return flag_range

    for extra in (
        _PATTERN_STANDARD_ROW,
        _PATTERN_FLAGGED_ROW,
        _PATTERN_INLINE_REF_TEXT,
        _PATTERN_PERCENT_ROW,
    ):
        match = extra.match(stripped)
        if match:
            groups = match.groupdict()
            try:
                value = _to_float(groups["value"])
                low = _to_float(groups["low"])
                high = _to_float(groups["high"])
            except (KeyError, ValueError):
                continue
            name = _parsed_test_name(groups["name"])
            if not name:
                continue
            unit = _clean_unit(groups.get("unit"))
            if extra is _PATTERN_PERCENT_ROW:
                unit = "%"
            return ParsedLabResult(
                raw_test_name=name,
                value=value,
                unit=unit,
                reference_range_low=low,
                reference_range_high=high,
                raw_line=stripped,
                parser_pattern="generic_regex",
            )

    bounded = _PATTERN_BOUNDED_VALUE.match(stripped)
    if bounded:
        groups = bounded.groupdict()
        try:
            value = _to_float(groups["bounded"])
        except ValueError:
            pass
        else:
            name = _parsed_test_name(groups["name"])
            if name:
                return ParsedLabResult(
                    raw_test_name=name,
                    value=value,
                    unit=_clean_unit(groups.get("unit")),
                    reference_range_low=None,
                    reference_range_high=None,
                    raw_line=stripped,
                    parser_pattern="generic_regex",
                )

    value_unit = _PATTERN_VALUE_UNIT_PARENS.match(stripped)
    if value_unit:
        groups = value_unit.groupdict()
        unit_raw = (groups.get("unit") or "").strip()
        if not re.search(r"\d+\s*[-–—]\s*\d+", unit_raw):
            try:
                value = _to_float(groups["value"])
            except ValueError:
                return None
            name = _parsed_test_name(groups["name"])
            if not name:
                return None
            return ParsedLabResult(
                raw_test_name=name,
                value=value,
                unit=_clean_unit(unit_raw),
                reference_range_low=None,
                reference_range_high=None,
                raw_line=stripped,
            )

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
        name = _parsed_test_name(groups["name"])
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


_LAB_ROW_NAME_REST = re.compile(r"^(.+?)(\s{2,}.+)$")


def postprocess_ocr_lab_text(text: str) -> str:
    """Fix per-token reversed OCR in analyte names before regex parsing."""
    from app.pipeline.user_biomarker_profile import (
        _fix_ocr_reversed_name,
        _looks_ocr_reversed,
        resolve_canonical_name,
    )

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        match = _LAB_ROW_NAME_REST.match(stripped)
        if match:
            name, rest = match.group(1), match.group(2)
            fixed = _fix_ocr_reversed_name(name)
            if fixed != name:
                orig_resolved = resolve_canonical_name(name)
                fixed_resolved = resolve_canonical_name(fixed)
                has_reversed_token = any(_looks_ocr_reversed(token) for token in name.split())
                if not orig_resolved and fixed_resolved:
                    line = f"{fixed}{rest}"
                elif orig_resolved and not fixed_resolved:
                    pass
                elif has_reversed_token:
                    line = f"{fixed}{rest}"
        lines.append(line)
    return "\n".join(lines)


def parse_lab_text_legacy_regex(text: str) -> list[ParsedLabResult]:
    """Legacy regex-only parse (line by line, no provider detection)."""
    text = postprocess_ocr_lab_text(text)
    results: list[ParsedLabResult] = []
    for line in text.splitlines():
        parsed = parse_lab_line(line)
        if parsed is not None:
            results.append(parsed)
    return results


def parse_lab_text(text: str, *, filename: str = "", file_bytes: bytes | None = None) -> list[ParsedLabResult]:
    """Parse lab report text via the document intelligence pipeline."""
    from app.pipeline.parsers.pipeline import run_document_pipeline

    outcome = run_document_pipeline(text, filename=filename, file_bytes=file_bytes)
    return outcome.results


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


def extract_document_text(file_bytes: bytes, filename: str) -> str:
    """Return plain text from a lab file (PDF via pdfplumber + tesseract, else UTF-8 decode)."""
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    return file_bytes.decode("utf-8", errors="replace")


def parse_lab_file(file_bytes: bytes, filename: str) -> list[ParsedLabResult]:
    """Dispatch on file extension: OCR/extract PDFs, decode everything else as text."""
    text = extract_document_text(file_bytes, filename)
    return parse_lab_text(text, filename=filename, file_bytes=file_bytes)


def parse_lab_document(file_bytes: bytes, filename: str):
    """Full parse outcome including unparsed lines and provider detection."""
    from app.pipeline.parsers.pipeline import run_document_pipeline

    text = extract_document_text(file_bytes, filename)
    return run_document_pipeline(text, filename=filename, file_bytes=file_bytes)


def parse_lab_file_with_llm_fallback(file_bytes: bytes, filename: str) -> list[ParsedLabResult]:
    """Document intelligence pipeline first; fall back to LLM text/vision when empty."""
    text = extract_document_text(file_bytes, filename)
    parsed = parse_lab_text(text, filename=filename, file_bytes=file_bytes)
    if parsed:
        return parsed

    from app.config import settings

    if not settings.openai_api_key:
        return []

    from app.pipeline.llm_lab_parser import LLMLabParserError, parse_lab_pdf_with_vision, parse_lab_text_with_llm

    try:
        if text.strip():
            parsed = parse_lab_text_with_llm(text)
            if parsed:
                return parsed

        if filename.lower().endswith(".pdf"):
            parsed = parse_lab_pdf_with_vision(file_bytes)
            if parsed:
                return parsed
    except LLMLabParserError:
        return []
    except Exception:
        return []

    return []
