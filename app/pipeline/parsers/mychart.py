"""Epic MyChart lab document parser.

Primary path for **Result Trends** PDFs (multi-date columns):
  Component | date1 | date2 | … | latest_date
  → use the **latest** non-empty date column (usually rightmost).

Also covers single-result MyChart print views and stacked text layouts.

Filename cue: "Result Trends - CBC and differential - Aug 6, 2026.pdf"
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from app.pipeline.parsers.base import ParserPassResult
from app.pipeline.user_biomarker_profile import clean_parsed_test_name, resolve_canonical_name
from app.schemas.pipeline import ParsedLabResult

_NUM = r"[<>]?\s*-?\d+\.?\d*"
_NUMERIC = re.compile(rf"^{_NUM}$")
_VALUE_CELL = re.compile(
    rf"(?P<value>{_NUM})\s*(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?",
    re.IGNORECASE,
)
_FLAG_WORD = re.compile(r"\b(High|Low|HH|LL|Critical|Abnormal)\b", re.IGNORECASE)
_RANGE_IN_TEXT = re.compile(
    rf"(?:Normal|Standard|Reference)\s+Range\s*:?\s*"
    rf"(?:Not\s+Estab\.?|Not\s+Established|"
    rf"(?P<low>{_NUM})\s*[-–—]\s*(?P<high>{_NUM}))",
    re.IGNORECASE | re.DOTALL,
)
_DATE_HDR = re.compile(
    r"^(?P<m>[A-Za-z]{3,9})\s+(?P<d>\d{1,2}),\s*(?P<y>\d{4})$|"
    r"^(?P<m2>\d{1,2})/(?P<d2>\d{1,2})/(?P<y2>\d{2,4})$|"
    r"^(?P<y3>\d{4})-(?P<m3>\d{2})-(?P<d3>\d{2})$"
)
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_UNIT = re.compile(
    r"^(?:mg/dL|mg/L|g/dL|ng/mL|pg/mL|µIU/mL|uIU/mL|mIU/L|U/L|IU/L|mmol/L|µmol/L|mcg/dL|"
    r"K/uL|K/µL|x10E3/uL|x10E3/µL|x10E6/uL|x10E6/µL|x10\^3/uL|10\^3/uL|%|ratio|ug/dL|"
    r"mcg/L|cells/uL|fL|pg|g/L|thou/uL|mil/uL|mEq/L|mL/min.*)?$",
    re.IGNORECASE,
)

_SKIP = re.compile(
    r"^(?:Result Trends|Compare result trends|Test Results|Lab Results|Results|"
    r"Component|Your Value|Value|Standard Range|Reference Range|Flag|Status|"
    r"Collected|Collection Date|Resulted|Result Date|Ordering Provider|"
    r"MyChart|Epic|Powered by Epic|Page \d|Results limited|Results found|"
    r"Date of Birth|Table \d)",
    re.IGNORECASE,
)

_NAME_LIKE = re.compile(r"^[A-Za-z%/][A-Za-z0-9/(),.'%\-# ]{1,90}$")
_FLAG = re.compile(r"^(?:H|L|\*|HIGH|LOW|ABNORMAL|HH|LL)$", re.IGNORECASE)
_RANGE_DASH = re.compile(
    rf"^(?P<low>{_NUM})\s*[-–—to]+\s*(?P<high>{_NUM})\s*(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.]*)?\s*$",
    re.IGNORECASE,
)
_RANGE_LT = re.compile(rf"^<\s*(?:=?\s*)?(?P<high>{_NUM})\s*(?P<unit>.*)?$")
_RANGE_GT = re.compile(rf"^>\s*(?:=?\s*)?(?P<low>{_NUM})\s*(?P<unit>.*)?$")

_INLINE_STD_RANGE = re.compile(
    rf"^(?P<name>[A-Za-z%/][A-Za-z0-9/(),.'%\-# ]{{1,60}}?)\s+"
    rf"(?P<value>{_NUM})\s+"
    rf"(?:(?P<flag>H|L|\*|HIGH|LOW)\s+)?"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?\s+"
    rf"(?:Standard|Reference|Normal)\s+Range\s*:?\s*"
    rf"(?P<range>.+?)\s*$",
    re.IGNORECASE,
)

_INLINE_ROW = re.compile(
    rf"^(?P<name>[A-Za-z%/][A-Za-z0-9/(),.'%\-# ]{{1,60}}?)\s{{1,}}"
    rf"(?P<value>{_NUM})\s*"
    rf"(?:(?P<flag>H|L|\*|HIGH|LOW)\s+)?"
    rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?\s*"
    rf"(?P<low>{_NUM})\s*[-–—]\s*(?P<high>{_NUM})\s*"
    rf"(?P<unit2>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?\s*$",
    re.IGNORECASE,
)


def _to_float(raw: str) -> float:
    return float(str(raw).strip().lstrip("<>").strip())


def _normalize_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    unit = str(raw).strip().strip("()").strip()
    unit = unit.replace("μ", "µ")
    return unit or None


def _parse_date_header(cell: str) -> datetime | None:
    text = re.sub(r"\s+", " ", (cell or "").strip())
    if not text or text.lower() == "component":
        return None
    m = _DATE_HDR.match(text)
    if not m:
        return None
    if m.group("m"):
        mon = _MONTHS.get(m.group("m").lower()[:3]) or _MONTHS.get(m.group("m").lower())
        if not mon:
            return None
        return datetime(int(m.group("y")), mon, int(m.group("d")))
    if m.group("m2"):
        y = int(m.group("y2"))
        if y < 100:
            y += 2000
        return datetime(y, int(m.group("m2")), int(m.group("d2")))
    if m.group("y3"):
        return datetime(int(m.group("y3")), int(m.group("m3")), int(m.group("d3")))
    return None


def _parse_component_meta(cell: str) -> tuple[str, float | None, float | None, str | None]:
    """Extract name, ref low/high, unit from the Component column cell.

    MyChart often splits ranges across lines::

        Hemoglobin
        Normal Range: 11.1 -
        15.9 g/dL
    """
    raw = (cell or "").strip()
    if not raw:
        return "", None, None, None

    low: float | None = None
    high: float | None = None
    unit: str | None = None

    # Single-line or re.DOTALL multi-line complete range
    range_m = re.search(
        rf"(?:Normal|Standard|Reference)\s+Range\s*:?\s*"
        rf"(?P<low>{_NUM})\s*[-–—]\s*(?P<high>{_NUM})\s*"
        rf"(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?",
        raw,
        re.IGNORECASE | re.DOTALL,
    )
    if range_m:
        low = _to_float(range_m.group("low"))
        high = _to_float(range_m.group("high"))
        unit = _normalize_unit(range_m.group("unit"))

    name_parts: list[str] = []
    in_range_block = False
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        if re.match(r"^(?:Normal|Standard|Reference)\s+Range", line, re.I):
            in_range_block = True
            # Partial: "Normal Range: 3.77 -" (high on next line)
            partial = re.search(rf"(?P<low>{_NUM})\s*[-–—]\s*$", line)
            if partial and low is None:
                low = _to_float(partial.group("low"))
            full = re.search(
                rf"(?P<low>{_NUM})\s*[-–—]\s*(?P<high>{_NUM})\s*(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?",
                line,
                re.I,
            )
            if full:
                low = _to_float(full.group("low"))
                high = _to_float(full.group("high"))
                if full.group("unit"):
                    unit = _normalize_unit(full.group("unit"))
            if re.search(r"Not\s+Estab", line, re.I):
                in_range_block = True
            continue

        if in_range_block:
            # Continuation: "15.9 g/dL" or "Estab. %" or "5.28 x10E6/uL"
            if re.match(r"^Not\s+Estab", line, re.I) or re.match(r"^Estab\.?\s*%?$", line, re.I):
                continue
            cont = re.match(
                rf"^(?P<high>{_NUM})\s*(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?\s*$",
                line,
            )
            if cont:
                if high is None:
                    high = _to_float(cont.group("high"))
                if cont.group("unit") and not unit:
                    unit = _normalize_unit(cont.group("unit"))
                continue
            if re.fullmatch(
                r"(?:mg/dL|g/dL|%|fL|pg|x10E3/uL|x10E6/uL|K/uL|ng/mL|pg/mL|U/L|mmol/L|x10E3/µL)",
                line,
                re.I,
            ):
                unit = _normalize_unit(line)
                continue
            # Stop range block if unexpected content
            in_range_block = False

        if re.fullmatch(
            r"(?:mg/dL|g/dL|%|fL|pg|x10E3/uL|x10E6/uL|K/uL|ng/mL|pg/mL|U/L|mmol/L)",
            line,
            re.I,
        ):
            unit = _normalize_unit(line)
            continue
        if _FLAG.match(line) or line.lower() in {"high", "low"}:
            continue
        if re.match(r"^Estab\.?\s*%?$", line, re.I):
            continue
        name_parts.append(line)

    name = clean_parsed_test_name(" ".join(name_parts))
    # Guard: strip accidental trailing number/unit stuck on name
    name = re.sub(
        rf"\s+{_NUM}\s*(?:[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?\s*$",
        "",
        name,
    ).strip()
    return name, low, high, unit


def _parse_value_cell(cell: str) -> tuple[float | None, str | None]:
    """Parse '6.8 x10E3/uL' or '14.5 x10E3/uL\\nHigh' → value, unit."""
    text = (cell or "").strip()
    if not text:
        return None, None
    # Prefer first numeric token
    m = re.search(
        rf"(?P<value>{_NUM})\s*(?P<unit>[A-Za-z%/µμ][A-Za-z0-9%/µμ.^]*)?",
        text,
    )
    if not m:
        return None, None
    unit = _normalize_unit(m.group("unit"))
    return _to_float(m.group("value")), unit


def _latest_value_from_row(
    row: list,
    date_cols: list[tuple[int, datetime]],
) -> tuple[float | None, str | None, datetime | None]:
    """Pick the latest (by date) non-empty value among date columns."""
    best: tuple[datetime, float, str | None] | None = None
    for idx, dt in date_cols:
        if idx >= len(row):
            continue
        cell = row[idx]
        if cell is None or str(cell).strip() == "":
            continue
        val, unit = _parse_value_cell(str(cell))
        if val is None:
            continue
        if best is None or dt >= best[0]:
            best = (dt, val, unit)
    if best is None:
        return None, None, None
    return best[1], best[2], best[0]


def _find_header_and_dates(table: list[list]) -> tuple[int, int, list[tuple[int, datetime]]] | None:
    """Return (header_row_idx, component_col_idx, [(col_idx, date), ...])."""
    for r_idx, row in enumerate(table):
        if not row:
            continue
        date_cols: list[tuple[int, datetime]] = []
        component_col: int | None = None
        for c_idx, cell in enumerate(row):
            text = str(cell or "").strip()
            if not text:
                continue
            # Component label (may be first non-null)
            if text.lower() == "component" or text.lower().startswith("component"):
                component_col = c_idx
                continue
            dt = _parse_date_header(text)
            if dt is not None:
                date_cols.append((c_idx, dt))
        if date_cols and component_col is not None:
            date_cols.sort(key=lambda x: x[1])  # chronological
            return r_idx, component_col, date_cols
        # Header sometimes has no explicit "Component" but first string col + dates
        if date_cols and len(date_cols) >= 2:
            # first non-date non-empty col as component
            for c_idx, cell in enumerate(row):
                text = str(cell or "").strip()
                if not text:
                    continue
                if _parse_date_header(text):
                    continue
                if c_idx not in {c for c, _ in date_cols}:
                    component_col = c_idx
                    break
            if component_col is not None:
                date_cols.sort(key=lambda x: x[1])
                return r_idx, component_col, date_cols
    return None


def parse_mychart_result_trends_pdf(file_bytes: bytes) -> list[ParsedLabResult]:
    """Parse MyChart Result Trends PDF tables; keep **latest** date per component."""
    import pdfplumber

    results: list[ParsedLabResult] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table or len(table) < 2:
                        continue
                    found = _find_header_and_dates(table)
                    if not found:
                        continue
                    header_idx, comp_col, date_cols = found
                    for row in table[header_idx + 1 :]:
                        if not row or comp_col >= len(row):
                            continue
                        comp_cell = row[comp_col]
                        if comp_cell is None or str(comp_cell).strip() == "":
                            continue
                        name, low, high, unit_from_meta = _parse_component_meta(str(comp_cell))
                        if not name or len(name) < 2:
                            continue
                        if name.lower() in {"component", "result trends"}:
                            continue
                        value, unit_from_val, result_date = _latest_value_from_row(row, date_cols)
                        if value is None:
                            continue
                        unit = unit_from_val or unit_from_meta
                        date_note = result_date.strftime("%Y-%m-%d") if result_date else "latest"
                        results.append(
                            ParsedLabResult(
                                raw_test_name=name,
                                value=value,
                                unit=unit,
                                reference_range_low=low,
                                reference_range_high=high,
                                raw_line=f"{name}={value} ({date_note})",
                                parser_pattern="mychart_result_trends_latest",
                            )
                        )
    except Exception:
        return []
    return results


# ---------------------------------------------------------------------------
# Text-path fallbacks (single-result / stacked layouts)
# ---------------------------------------------------------------------------


def _is_skip_line(line: str) -> bool:
    if not line or len(line) < 2:
        return True
    if _SKIP.search(line):
        return True
    return False


def _looks_like_name(line: str) -> bool:
    if _is_skip_line(line) or _NUMERIC.match(line) or _FLAG.match(line):
        return False
    if _RANGE_DASH.match(line) or _UNIT.match(line):
        return False
    if not _NAME_LIKE.match(line):
        return False
    if resolve_canonical_name(line):
        return True
    return bool(re.search(r"[A-Za-z]{2,}", line))


def _parse_range_blob(blob: str) -> tuple[float | None, float | None, str | None]:
    blob = blob.strip()
    m = _RANGE_DASH.match(blob)
    if m:
        return _to_float(m.group("low")), _to_float(m.group("high")), _normalize_unit(m.group("unit"))
    m = _RANGE_LT.match(blob)
    if m:
        return None, _to_float(m.group("high")), _normalize_unit(m.group("unit"))
    m = _RANGE_GT.match(blob)
    if m:
        return _to_float(m.group("low")), None, _normalize_unit(m.group("unit"))
    return None, None, None


def normalize_mychart_text(text: str) -> str:
    lines_out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            lines_out.append("")
            continue
        line = re.sub(r"^[•·▪►>\-\u2022]+\s*", "", line)
        m = re.match(
            r"^(?:Standard|Reference|Normal)\s+Range\s*:?\s*(.+)$",
            line,
            re.I,
        )
        if m:
            lines_out.append(m.group(1).strip())
            continue
        lines_out.append(line)
    return "\n".join(lines_out)


def _make_result(
    name: str,
    value: float,
    *,
    unit: str | None = None,
    low: float | None = None,
    high: float | None = None,
    raw_line: str = "",
    pattern: str = "mychart",
) -> ParsedLabResult:
    return ParsedLabResult(
        raw_test_name=clean_parsed_test_name(name),
        value=value,
        unit=_normalize_unit(unit),
        reference_range_low=low,
        reference_range_high=high,
        raw_line=raw_line or name,
        parser_pattern=pattern,
    )


def _inline_pass(lines: list[str]) -> ParserPassResult:
    results: list[ParsedLabResult] = []
    consumed: set[int] = set()
    for idx, line in enumerate(lines):
        if not line or _is_skip_line(line):
            continue
        m = _INLINE_STD_RANGE.match(line)
        if m:
            low, high, unit = _parse_range_blob(m.group("range"))
            u = _normalize_unit(m.group("unit")) or unit
            results.append(
                _make_result(
                    m.group("name"),
                    _to_float(m.group("value")),
                    unit=u,
                    low=low,
                    high=high,
                    raw_line=line,
                    pattern="mychart_inline_std_range",
                )
            )
            consumed.add(idx)
            continue
        m = _INLINE_ROW.match(line)
        if m:
            unit = _normalize_unit(m.group("unit") or m.group("unit2"))
            results.append(
                _make_result(
                    m.group("name"),
                    _to_float(m.group("value")),
                    unit=unit,
                    low=_to_float(m.group("low")),
                    high=_to_float(m.group("high")),
                    raw_line=line,
                    pattern="mychart_inline_row",
                )
            )
            consumed.add(idx)
    return ParserPassResult(results=results, consumed_line_indices=consumed)


def _sliding_window_pass(lines: list[str], *, skip_indices: set[int] | None = None) -> ParserPassResult:
    skip = skip_indices or set()
    results: list[ParsedLabResult] = []
    consumed: set[int] = set()
    i = 0
    n = len(lines)
    while i < n:
        if i in skip or i in consumed:
            i += 1
            continue
        line = lines[i].strip() if lines[i] else ""
        if not line or not _looks_like_name(line):
            i += 1
            continue
        name = line
        name_idx = i
        j = i + 1
        while j < n and j not in skip:
            nxt = lines[j].strip() if lines[j] else ""
            if not nxt:
                j += 1
                continue
            combined = f"{name} {nxt}".strip()
            if _looks_like_name(nxt) and resolve_canonical_name(combined) and not resolve_canonical_name(name):
                name = combined
                consumed.add(j)
                j += 1
                continue
            break
        value: float | None = None
        unit: str | None = None
        low: float | None = None
        high: float | None = None
        value_idx: int | None = None
        k = j
        steps = 0
        while k < n and steps < 8:
            if k in skip:
                k += 1
                steps += 1
                continue
            token = lines[k].strip() if lines[k] else ""
            if not token:
                k += 1
                steps += 1
                continue
            if value is None and _NUMERIC.match(token):
                value = _to_float(token)
                value_idx = k
                k += 1
                steps += 1
                continue
            if value is not None and _FLAG.match(token):
                k += 1
                steps += 1
                continue
            if value is not None and unit is None and _UNIT.match(token):
                unit = _normalize_unit(token)
                k += 1
                steps += 1
                continue
            if value is not None and low is None and high is None:
                rl, rh, ru = _parse_range_blob(token)
                if rl is not None or rh is not None:
                    low, high = rl, rh
                    if ru and not unit:
                        unit = ru
                    k += 1
                    steps += 1
                    continue
            if value is not None and _looks_like_name(token):
                break
            if value is None and _looks_like_name(token):
                break
            k += 1
            steps += 1
        if value is not None:
            results.append(
                _make_result(
                    name,
                    value,
                    unit=unit,
                    low=low,
                    high=high,
                    raw_line=name,
                    pattern="mychart_sliding_window",
                )
            )
            consumed.add(name_idx)
            if value_idx is not None:
                consumed.add(value_idx)
            for t in range(name_idx, min(k, n)):
                if t not in skip:
                    consumed.add(t)
            i = k
            continue
        i += 1
    return ParserPassResult(results=results, consumed_line_indices=consumed)


def parse_mychart_text(text: str) -> ParserPassResult:
    """Parse MyChart text layouts (fallback when PDF table parse is empty)."""
    normalized = normalize_mychart_text(text)
    lines = [line.strip() for line in normalized.splitlines()]
    inline = _inline_pass(lines)
    window = _sliding_window_pass(lines, skip_indices=inline.consumed_line_indices)
    results = list(inline.results) + list(window.results)
    consumed = set(inline.consumed_line_indices) | set(window.consumed_line_indices)
    return ParserPassResult(results=results, consumed_line_indices=consumed)


def mychart_unparsed_lines(text: str, consumed: set[int]) -> list[str]:
    lines = [line.strip() for line in normalize_mychart_text(text).splitlines()]
    out: list[str] = []
    for i, line in enumerate(lines):
        if i in consumed or not line or _is_skip_line(line):
            continue
        out.append(line)
    return out
