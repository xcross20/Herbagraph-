"""Pass 1: structured table extraction from PDF lab reports via pdfplumber."""

from __future__ import annotations

import io
import re

from app.pipeline.lab_parser import parse_lab_line
from app.schemas.pipeline import ParsedLabResult

_NAME_HEADERS = frozenset({"test", "test name", "component", "analyte", "name", "assay"})
_VALUE_HEADERS = frozenset({"result", "value", "your value"})
_UNIT_HEADERS = frozenset({"unit", "units"})
_RANGE_HEADERS = frozenset({"reference", "reference range", "ref range", "normal range", "range"})
_FLAG_HEADERS = frozenset({"flag", "abnormal", "status"})


def _header_map(header_row: list[str | None]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        if not cell:
            continue
        key = re.sub(r"\s+", " ", str(cell).strip().lower())
        if key in _NAME_HEADERS or "test" in key or "component" in key:
            mapping.setdefault("name", idx)
        elif key in _VALUE_HEADERS or key == "result":
            mapping.setdefault("value", idx)
        elif key in _UNIT_HEADERS:
            mapping.setdefault("unit", idx)
        elif key in _RANGE_HEADERS or "reference" in key:
            mapping.setdefault("range", idx)
        elif key in _FLAG_HEADERS:
            mapping.setdefault("flag", idx)
    return mapping


def _row_from_table_cells(
    name: str,
    value_cell: str,
    *,
    unit_cell: str | None = None,
    range_cell: str | None = None,
    flag_cell: str | None = None,
) -> ParsedLabResult | None:
    parts = [name.strip()]
    if value_cell:
        parts.append(str(value_cell).strip())
    if flag_cell and str(flag_cell).strip():
        parts.append(str(flag_cell).strip())
    if unit_cell and str(unit_cell).strip():
        parts.append(str(unit_cell).strip())
    if range_cell and str(range_cell).strip():
        parts.append(str(range_cell).strip())

    synthetic = " ".join(p for p in parts if p)
    parsed = parse_lab_line(synthetic)
    if parsed is None and range_cell:
        parsed = parse_lab_line(f"{name} {value_cell} {range_cell}")
    if parsed is None:
        return None
    return parsed.model_copy(
        update={
            "parser_pattern": "table_extraction",
            "raw_line": synthetic,
        }
    )


def parse_pdf_tables(file_bytes: bytes) -> list[ParsedLabResult]:
    """Extract biomarker rows from PDF tables when column headers are recognizable."""
    import pdfplumber

    results: list[ParsedLabResult] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table or len(table) < 2:
                        continue
                    header = _header_map(table[0])
                    if "name" not in header or "value" not in header:
                        continue
                    for row in table[1:]:
                        if not row or len(row) <= max(header.values()):
                            continue
                        name = str(row[header["name"]] or "").strip()
                        value = str(row[header["value"]] or "").strip()
                        if not name or not value:
                            continue
                        unit = str(row[header["unit"]]).strip() if "unit" in header and row[header["unit"]] else None
                        range_cell = (
                            str(row[header["range"]]).strip() if "range" in header and row[header["range"]] else None
                        )
                        flag = str(row[header["flag"]]).strip() if "flag" in header and row[header["flag"]] else None
                        parsed = _row_from_table_cells(name, value, unit_cell=unit, range_cell=range_cell, flag_cell=flag)
                        if parsed is not None:
                            results.append(parsed)
    except Exception:
        return []
    return results