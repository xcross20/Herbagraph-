"""Document intelligence pipeline: detect provider → normalize → parse → score."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.document_detection import LabDocumentProvider, detect_lab_document_provider
from app.pipeline.parse_confidence import apply_confidence_scores
from app.pipeline.parsers.base import ParserPassResult, dedupe_parsed_results
from app.pipeline.parsers.healow import healow_unparsed_lines, parse_healow_text
from app.pipeline.table_parser import parse_pdf_tables
from app.schemas.pipeline import ParsedLabResult


@dataclass
class ParseDocumentOutcome:
    results: list[ParsedLabResult] = field(default_factory=list)
    unparsed_lines: list[str] = field(default_factory=list)
    provider: LabDocumentProvider = LabDocumentProvider.GENERIC
    passes_used: list[str] = field(default_factory=list)


def _generic_line_pass(text: str, *, skip_lines: set[str] | None = None) -> ParserPassResult:
    from app.pipeline.lab_parser import parse_lab_line, postprocess_ocr_lab_text

    skip = {line.strip().lower() for line in (skip_lines or set()) if line.strip()}
    processed = postprocess_ocr_lab_text(text)
    results: list[ParsedLabResult] = []
    consumed: set[int] = set()

    lines = processed.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.lower() in skip:
            continue
        parsed = parse_lab_line(stripped)
        if parsed is not None:
            results.append(
                parsed.model_copy(
                    update={
                        "parser_pattern": parsed.parser_pattern or "generic_regex",
                        "raw_line": stripped,
                    }
                )
            )
            consumed.add(idx)

    return ParserPassResult(results=results, consumed_line_indices=consumed)


def _generic_sliding_window(text: str, consumed_indices: set[int]) -> ParserPassResult:
    """Pass 3b: generic vertical reconstruction for non-Healow stacked OCR layouts."""
    from app.pipeline.parsers.healow import _sliding_window_pass  # shared vertical assembler

    lines = [line.strip() for line in text.splitlines()]
    window = _sliding_window_pass(lines, skip_indices=consumed_indices)
    for row in window.results:
        row.parser_pattern = "generic_sliding_window"
    return window


def run_document_pipeline(
    text: str,
    *,
    filename: str = "",
    file_bytes: bytes | None = None,
) -> ParseDocumentOutcome:
    """Run provider detection and layered parsing passes with confidence scoring."""
    provider = detect_lab_document_provider(text, filename)
    passes: list[str] = []
    all_results: list[ParsedLabResult] = []
    consumed_line_indices: set[int] = set()

    # Pass 1: PDF table extraction
    if file_bytes and filename.lower().endswith(".pdf"):
        table_rows = parse_pdf_tables(file_bytes)
        if table_rows:
            passes.append("table_extraction")
            all_results.extend(table_rows)

    # Pass 2: provider-specific parser
    healow = ParserPassResult()
    if provider == LabDocumentProvider.HEALOW:
        healow = parse_healow_text(text)
        if healow.results:
            passes.append("healow_parser")
            all_results.extend(healow.results)
            consumed_line_indices = healow.consumed_line_indices

    # Pass 3: generic regex line parser
    generic = _generic_line_pass(text)
    if generic.results:
        passes.append("generic_regex")
        all_results.extend(generic.results)
        consumed_line_indices |= generic.consumed_line_indices

    # Pass 4: sliding window for stacked lines not yet consumed
    if provider == LabDocumentProvider.HEALOW:
        unparsed = healow_unparsed_lines(text, consumed_line_indices)
    else:
        lines = [line.strip() for line in text.splitlines()]
        unparsed = [lines[i] for i in range(len(lines)) if i not in consumed_line_indices and lines[i].strip()]

    if unparsed:
        window = _generic_sliding_window(text, consumed_line_indices)
        if window.results:
            passes.append("generic_sliding_window")
            all_results.extend(window.results)
            consumed_line_indices |= window.consumed_line_indices

    deduped = dedupe_parsed_results(all_results)
    scored = apply_confidence_scores(deduped, document_provider=provider.value)

    # Final unparsed lines for manual review surfacing
    lines = text.splitlines()
    if provider == LabDocumentProvider.HEALOW:
        remaining = healow_unparsed_lines(text, consumed_line_indices)
    else:
        remaining = [
            lines[i].strip()
            for i in range(len(lines))
            if i not in consumed_line_indices and lines[i].strip()
        ]

    return ParseDocumentOutcome(
        results=scored,
        unparsed_lines=remaining[:40],
        provider=provider,
        passes_used=passes or ["none"],
    )