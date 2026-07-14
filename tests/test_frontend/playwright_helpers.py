"""Shared Playwright helpers for HerbaGraph UI smoke tests."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
SCENARIOS_RAW = ROOT / "samples" / "lab_scenarios" / "raw"

FAILURE_PATTERNS = (
    re.compile(r"lab processing failed", re.I),
    re.compile(r"report generation failed", re.I),
    re.compile(r"no biomarkers were parsed", re.I),
    re.compile(r"abnormal labs were parsed but no pathway signals", re.I),
    re.compile(r"no recommendations were surfaced.*did not parse correctly", re.I),
)


def playwright_enabled() -> bool:
    return os.environ.get("HERBAGRAPH_PLAYWRIGHT", "0") == "1"


def ui_base_url() -> str:
    return os.environ.get("HERBAGRAPH_UI_BASE", "http://localhost:8000").rstrip("/")


def require_playwright_stack():
    if not playwright_enabled():
        pytest.skip("Set HERBAGRAPH_PLAYWRIGHT=1 to run Playwright UI smoke tests")
    pytest.importorskip("playwright")


def assert_no_ui_failure_copy(page) -> None:
    status = page.locator("#status-line")
    if status.count():
        status_class = status.get_attribute("class") or ""
        status_text = (status.inner_text() or "").strip()
        assert "error" not in status_class, f"status-line error: {status_text}"
        for pattern in FAILURE_PATTERNS:
            assert not pattern.search(status_text), f"status-line: {status_text}"

    for selector in ("#executive-summary-body", "#biological-network-body", "#intervention-library-body"):
        body = page.locator(selector)
        if not body.count():
            continue
        text = body.inner_text() or ""
        for pattern in FAILURE_PATTERNS:
            assert not pattern.search(text), f"{selector}: {text[:300]}"


def wait_for_report_ready(page, *, timeout_ms: int = 180_000) -> None:
    page.wait_for_url(re.compile(r"report\.html\?report_id="), timeout=timeout_ms)
    page.wait_for_selector("#report", state="visible", timeout=timeout_ms)
    page.wait_for_function(
        """() => {
          const recs = document.getElementById('intervention-library-body');
          const hasRec = recs && recs.innerText && recs.innerText.trim().length > 20;
          const systems = document.getElementById('biological-network-body');
          const hasTable = systems && systems.querySelector('table');
          return hasRec || hasTable;
        }""",
        timeout=timeout_ms,
    )


def upload_and_analyze(page, fixture_path: Path) -> None:
    page.wait_for_selector("#upload-files", state="visible", timeout=30_000)
    page.set_input_files("#upload-files", str(fixture_path))
    page.click("#upload-btn")
    page.wait_for_selector("#upload-status", state="visible", timeout=30_000)
    page.wait_for_function(
        """() => {
          const el = document.getElementById('upload-status');
          return el && (el.textContent || '').toLowerCase().includes('upload complete');
        }""",
        timeout=180_000,
    )
    patient_id = page.evaluate("""() => {
      const m = location.hash.match(/#patient\\/([^/]+)/);
      return m ? m[1] : '';
    }""")
    page.goto(f"{ui_base_url()}/app.html#analysis?patient={patient_id}", wait_until="domcontentloaded")
    page.wait_for_selector("#run-analysis-btn", timeout=30_000)
    page.click("#run-analysis-btn")
    wait_for_report_ready(page)