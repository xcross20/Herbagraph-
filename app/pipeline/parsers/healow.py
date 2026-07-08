"""Healow / eClinicalWorks lab document parser.

Healow exports are layout-inconsistent (portal PDF, print-to-PDF, fax OCR, embedded
Quest/LabCorp rows). This parser normalizes portal phrasing, merges wrapped analyte
names, runs single-line regex where possible, then reconstructs vertical/stacked rows
with a sliding-window state machine.
"""

from __future__ import annotations

import re

from app.pipeline.parsers.base import ParserPassResult
from app.pipeline.user_biomarker_profile import clean_parsed_test_name, resolve_canonical_name
from app.schemas.pipeline import ParsedLabResult

_NUMERIC = re.compile(r"^[<>]?\s*-?\d+\.?\d*$")
_FLAG = re.compile(
    r"^(?:H|L|\*|HIGH|LOW|ABNORMAL|A|NEAR\s+OPTIMAL|BORDERLINE\s+HIGH|BORDERLINE\s+LOW|OPTIMAL)$",
    re.IGNORECASE,
)
_RANGE_DASH = re.compile(
    r"^(?P<low>\d+\.?\d*)\s*[-–—to]+\s*(?P<high>\d+\.?\d*)\s*(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ]*)?\s*$",
    re.IGNORECASE,
)
_RANGE_LT = re.compile(r"^<\s*(?P<high>\d+\.?\d*)\s*(?P<unit>[A-Za-z%/µμ%][A-Za-z0-9%/µμ%]*)?\s*$")
_RANGE_LTE = re.compile(r"^<=\s*(?P<high>\d+\.?\d*)\s*(?P<unit>[A-Za-z%/µμ%][A-Za-z0-9%/µμ%]*)?\s*$")
_UNIT = re.compile(
    r"^(?:mg/dL|mg/L|g/dL|ng/mL|pg/mL|µIU/mL|uIU/mL|mIU/L|U/L|IU/L|mmol/L|µmol/L|mcg/dL|"
    r"K/uL|x10E3/uL|%|ratio|ug/dL|mcg/L|cells/uL|fL|pg|g/L)\s*$",
    re.IGNORECASE,
)
_REF_PHRASE = re.compile(
    r"^(?:Normal value|Ref(?:erence)?(?:\s+Range)?|Normal Range|Expected|Normal)\s*:?\s*(.+)$",
    re.IGNORECASE,
)

_HEALOW_SKIP = re.compile(
    r"^(?:FINAL RESULT|Accession|Order Date|Collection Date|Received:|Report:|"
    r"Requesting Physician|Ordering Physician|Result:|Notes:|Summary generated|"
    r"Reference ranges based|Patient|DOB|MRN|FIN|Lab Ref ID|"
    r"Passion Health|Care -|^\d{3}-\d{3}-\d{4}$|"
    r"^-?\s*PREDIABETIC|^-?\s*DIABETIC|^-?\s*NORMAL)",
    re.IGNORECASE,
)

_NAME_LIKE = re.compile(r"^[A-Za-z%/][A-Za-z0-9/(),.'%\- ]{1,80}$")


def _to_float(raw: str) -> float:
    return float(raw.strip().lstrip("<>").strip())


def _normalize_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    unit = raw.strip().strip("()").strip()
    unit = unit.replace("μ", "µ")
    return unit or None


def _is_skip_line(line: str) -> bool:
    if not line or len(line) < 2:
        return True
    if _HEALOW_SKIP.search(line):
        return True
    if "@" in line and "." in line:
        return True
    return False


def _looks_like_name_line(line: str) -> bool:
    if _is_skip_line(line):
        return False
    if _NUMERIC.match(line) or _FLAG.match(line) or _RANGE_DASH.match(line):
        return False
    if _RANGE_LT.match(line) or _RANGE_LTE.match(line) or _UNIT.match(line):
        return False
    if not _NAME_LIKE.match(line):
        return False
    if resolve_canonical_name(line):
        return True
    # Healow panel headers like "Hemoglobin A1c" before F-prefixed rows.
    return bool(re.search(r"[A-Za-z]{3,}", line)) and not re.search(r"\d{2,}", line)


def normalize_healow_text(text: str) -> str:
    """Normalize Healow phrasing and merge wrapped biomarker names."""
    raw_lines = [line.strip() for line in text.splitlines()]
    normalized: list[str] = []

    for line in raw_lines:
        if not line:
            normalized.append("")
            continue
        ref_match = _REF_PHRASE.match(line)
        if ref_match:
            normalized.append(ref_match.group(1).strip())
            continue
        normalized.append(line)

    merged = _merge_wrapped_biomarker_names(normalized)
    merged = _attach_orphan_range_lines(merged)
    return "\n".join(merged)


def _attach_orphan_range_lines(lines: list[str]) -> list[str]:
    """Attach standalone range lines to the nearest prior value/name row (skip flag-only lines)."""
    attached: list[str] = []
    for line in lines:
        if not line:
            attached.append("")
            continue
        if attached and (_RANGE_DASH.match(line) or _RANGE_LT.match(line) or _RANGE_LTE.match(line)):
            target_idx = len(attached) - 1
            while target_idx >= 0 and attached[target_idx] and _FLAG.match(attached[target_idx]):
                target_idx -= 1
            if target_idx >= 0 and attached[target_idx]:
                prev = attached[target_idx]
                # Vertical stacks keep range on its own line (value line is numeric-only).
                if _NUMERIC.match(prev) or _UNIT.match(prev) or _FLAG.match(prev):
                    attached.append(line)
                else:
                    attached[target_idx] = f"{prev} {line}"
                continue
        attached.append(line)
    return attached


def _merge_wrapped_biomarker_names(lines: list[str]) -> list[str]:
    """Pattern E: merge wrapped analyte names split across lines."""
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            merged.append("")
            i += 1
            continue

        if i + 1 < len(lines) and lines[i + 1]:
            combined = f"{line} {lines[i + 1]}".strip()
            if (
                _looks_like_name_line(line)
                and _looks_like_name_line(lines[i + 1])
                and resolve_canonical_name(combined)
                and not resolve_canonical_name(line)
            ):
                merged.append(combined)
                i += 2
                continue

        merged.append(line)
        i += 1
    return merged


def _parse_line_regex(line: str) -> ParsedLabResult | None:
    from app.pipeline.lab_parser import parse_lab_line

    parsed = parse_lab_line(line)
    if parsed is None:
        return None
    return parsed.model_copy(
        update={
            "parser_pattern": "healow_line",
            "raw_line": line,
        }
    )


def _assemble_vertical_window(window: list[str]) -> ParsedLabResult | None:
    """Reconstruct a row from vertically stacked Healow lines (Pattern D)."""
    if len(window) < 2:
        return None

    value_idx = flag_idx = unit_idx = range_idx = None
    name_parts: list[str] = []

    for idx, line in enumerate(window):
        if _NUMERIC.match(line):
            if value_idx is None:
                value_idx = idx
            continue
        if _FLAG.match(line) and flag_idx is None:
            flag_idx = idx
            continue
        if _UNIT.match(line) and unit_idx is None:
            unit_idx = idx
            continue
        if _RANGE_DASH.match(line) or _RANGE_LT.match(line) or _RANGE_LTE.match(line):
            if range_idx is None:
                range_idx = idx
            continue
        if _looks_like_name_line(line):
            name_parts.append(line)

    if value_idx is None or not name_parts:
        return None

    if range_idx is None and unit_idx is None:
        return None

    raw_name = clean_parsed_test_name(" ".join(name_parts))
    if not raw_name or _is_skip_line(raw_name):
        return None

    try:
        value = _to_float(window[value_idx])
    except ValueError:
        return None

    unit = _normalize_unit(window[unit_idx]) if unit_idx is not None else None
    low: float | None = 0.0
    high: float | None = None

    if range_idx is not None:
        range_line = window[range_idx]
        dash = _RANGE_DASH.match(range_line)
        if dash:
            low = _to_float(dash.group("low"))
            high = _to_float(dash.group("high"))
            if not unit and dash.group("unit"):
                unit = _normalize_unit(dash.group("unit"))
        else:
            lt = _RANGE_LT.match(range_line) or _RANGE_LTE.match(range_line)
            if lt:
                high = _to_float(lt.group("high"))
                low = 0.0
                if not unit and lt.group("unit"):
                    unit = _normalize_unit(lt.group("unit"))

    raw_line = " | ".join(window)
    return ParsedLabResult(
        raw_test_name=raw_name,
        value=value,
        unit=unit,
        reference_range_low=low,
        reference_range_high=high,
        raw_line=raw_line,
        parser_pattern="healow_sliding_window",
    )


def _sliding_window_pass(lines: list[str], *, skip_indices: set[int]) -> ParserPassResult:
    results: list[ParsedLabResult] = []
    consumed: set[int] = set()
    non_empty = [(i, line) for i, line in enumerate(lines) if line.strip() and i not in skip_indices]

    for pos, (line_idx, line) in enumerate(non_empty):
        if line_idx in consumed:
            continue
        window_lines = [line]
        window_indices = [line_idx]
        for j in range(pos + 1, min(pos + 6, len(non_empty))):
            next_idx, next_line = non_empty[j]
            if next_idx in consumed:
                break
            window_lines.append(next_line)
            window_indices.append(next_idx)
            assembled = _assemble_vertical_window(window_lines)
            if assembled is not None:
                results.append(assembled)
                consumed.update(window_indices)
                break

    return ParserPassResult(results=results, consumed_line_indices=consumed)


def parse_healow_text(text: str) -> ParserPassResult:
    """Full Healow parse: normalize → line regex → vertical sliding window."""
    normalized = normalize_healow_text(text)
    lines = [line.strip() for line in normalized.splitlines()]

    results: list[ParsedLabResult] = []
    consumed: set[int] = set()

    for idx, line in enumerate(lines):
        if not line or _is_skip_line(line):
            continue
        parsed = _parse_line_regex(line)
        if parsed is not None:
            results.append(parsed)
            consumed.add(idx)

    window_result = _sliding_window_pass(lines, skip_indices=consumed)
    results.extend(window_result.results)
    consumed.update(window_result.consumed_line_indices)

    return ParserPassResult(results=results, consumed_line_indices=consumed)


def healow_unparsed_lines(text: str, consumed_indices: set[int]) -> list[str]:
    lines = [line.strip() for line in normalize_healow_text(text).splitlines()]
    return [
        lines[i]
        for i in range(len(lines))
        if i not in consumed_indices and lines[i].strip() and not _is_skip_line(lines[i])
    ]