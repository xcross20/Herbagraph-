"""Adversarial lab-text mutations for resilience testing.

Portal exports, OCR, and PDF column bleed create predictable failure modes.
These mutations simulate them across the full scenario matrix.
"""

from __future__ import annotations

import re
from typing import Callable

# Lines that look like analyte rows (name + numeric value), not headers/notes.
_NUMERIC_ROW_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9\s,()/.\-+%]+?)\s+(\d+\.?\d*)",
)

MUTATION_IDS = (
    "f_column_prefix",
    "double_spaces",
    "lowercase_names",
    "comma_total_suffix",
    "leading_final_flag",
)


def _mutate_f_column_prefix(line: str) -> str:
    m = _NUMERIC_ROW_RE.match(line.strip())
    if not m or line.strip().upper().startswith("F "):
        return line
    return f"F {line}"


def _mutate_double_spaces(line: str) -> str:
    m = _NUMERIC_ROW_RE.match(line.strip())
    if not m:
        return line
    name, rest = m.group(1), line[m.end(1) :]
    return f"{name}  {rest.lstrip()}"


def _mutate_lowercase_names(line: str) -> str:
    m = _NUMERIC_ROW_RE.match(line.strip())
    if not m:
        return line
    return f"{m.group(1).lower()}{line[m.end(1) :]}"


def _mutate_comma_total_suffix(line: str) -> str:
    m = _NUMERIC_ROW_RE.match(line.strip())
    if not m:
        return line
    name = m.group(1)
    if "cholesterol" in name.lower() and ", total" not in name.lower():
        return line.replace(name, f"{name}, Total", 1)
    return line


def _mutate_leading_final_flag(line: str) -> str:
    m = _NUMERIC_ROW_RE.match(line.strip())
    if not m or line.strip().upper().startswith("FINAL "):
        return line
    return f"FINAL {line}"


_MUTATORS: dict[str, Callable[[str], str]] = {
    "f_column_prefix": _mutate_f_column_prefix,
    "double_spaces": _mutate_double_spaces,
    "lowercase_names": _mutate_lowercase_names,
    "comma_total_suffix": _mutate_comma_total_suffix,
    "leading_final_flag": _mutate_leading_final_flag,
}


def apply_mutation(text: str, mutation_id: str) -> str:
    """Return lab text with one adversarial mutation applied line-by-line."""
    if mutation_id not in _MUTATORS:
        raise ValueError(f"unknown mutation: {mutation_id}")
    mutator = _MUTATORS[mutation_id]
    return "\n".join(mutator(line) for line in text.splitlines())


def all_mutations(text: str) -> list[tuple[str, str]]:
    """Apply every mutation; return (mutation_id, mutated_text) pairs."""
    return [(mid, apply_mutation(text, mid)) for mid in MUTATION_IDS]