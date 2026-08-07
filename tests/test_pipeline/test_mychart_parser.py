"""MyChart / Epic Result Trends and portal export parsing."""

from pathlib import Path

import pytest

from app.pipeline.document_detection import LabDocumentProvider, detect_lab_document_provider
from app.pipeline.lab_parser import parse_lab_document
from app.pipeline.parsers.mychart import parse_mychart_text
from app.pipeline.parsers.pipeline import run_document_pipeline

pytestmark = pytest.mark.unit

_SCENARIO_DIR = Path(__file__).resolve().parents[2] / "samples" / "lab_scenarios" / "raw"


def test_detect_mychart_from_filename_result_trends():
    assert (
        detect_lab_document_provider(
            "WBC\n5.2",
            filename="Result Trends - CBC and differential - Aug 6, 2026.pdf",
        )
        == LabDocumentProvider.MYCHART
    )


def test_detect_mychart_from_branding():
    text = "Test Results\nMyChart\nPowered by Epic\nGlucose 95"
    assert detect_lab_document_provider(text) == LabDocumentProvider.MYCHART


def test_detect_mychart_standard_range_component():
    text = "Component\nYour Value\nStandard Range\nWBC 5.2"
    assert detect_lab_document_provider(text) == LabDocumentProvider.MYCHART


def test_mychart_stacked_cbc_trends_fixture():
    text = (_SCENARIO_DIR / "format_mychart_cbc_trends.txt").read_text(encoding="utf-8")
    assert detect_lab_document_provider(text, "Result Trends - CBC.pdf") == LabDocumentProvider.MYCHART
    outcome = parse_mychart_text(text)
    names = {r.raw_test_name.lower() for r in outcome.results}
    assert "wbc" in names or any("wbc" in n for n in names)
    assert any(r.value == 5.2 for r in outcome.results)
    assert any(r.value == 12.1 for r in outcome.results)  # Hemoglobin with L flag
    assert len(outcome.results) >= 6


def test_mychart_inline_standard_range_fixture():
    text = (_SCENARIO_DIR / "format_mychart_inline_cmp.txt").read_text(encoding="utf-8")
    # Prefer full pipeline (generic + mychart) for mixed inline exports
    outcome = run_document_pipeline(text, filename="mychart_cmp.txt")
    glucose = next((r for r in outcome.results if "glucose" in r.raw_test_name.lower()), None)
    assert glucose is not None
    assert glucose.value == 102.0


def test_document_pipeline_uses_mychart_pass():
    text = (_SCENARIO_DIR / "format_mychart_cbc_trends.txt").read_text(encoding="utf-8")
    outcome = run_document_pipeline(text, filename="Result Trends - CBC and differential - Aug 6, 2026.pdf")
    assert outcome.provider == LabDocumentProvider.MYCHART
    assert "mychart_parser" in outcome.passes_used
    assert len(outcome.results) >= 5


def test_parse_lab_document_mychart_bytes():
    text = (_SCENARIO_DIR / "format_mychart_inline_cmp.txt").read_text(encoding="utf-8")
    outcome = parse_lab_document(text.encode("utf-8"), "mychart_cmp.txt")
    rows = outcome.results if hasattr(outcome, "results") else outcome
    assert len(rows) >= 4


def test_real_result_trends_pdf_uses_latest_date():
    """Regression: multi-date MyChart PDF must take Jul 10, 2026 (latest), not older columns."""
    pdf = Path("/Users/immanuellewis/Downloads/Result Trends - CBC and differential - Aug 6, 2026.pdf")
    if not pdf.is_file():
        pytest.skip("local MyChart PDF not present")
    from app.pipeline.parsers.mychart import parse_mychart_result_trends_pdf

    rows = parse_mychart_result_trends_pdf(pdf.read_bytes())
    by = {r.raw_test_name.lower(): r for r in rows}
    assert len(rows) >= 15
    wbc = by.get("white blood cell count")
    assert wbc is not None and wbc.value == 6.8  # latest, not 14.5 (Jan 2025 high)
    hgb = by.get("hemoglobin")
    assert hgb is not None and hgb.value == 12.1  # latest, not 8.2 (Mar 2026 low)
    plt = by.get("platelets")
    assert plt is not None and plt.value == 393.0  # latest, not 509
    assert "2026-07-10" in (wbc.raw_line or "")
