"""Playwright UI smoke — real browser upload → report against a running stack.

Skipped unless HERBAGRAPH_PLAYWRIGHT=1 and playwright is installed.

  pip install playwright
  playwright install chromium
  docker compose up -d && docker compose restart worker api
  HERBAGRAPH_PLAYWRIGHT=1 pytest tests/test_frontend/test_playwright_ui_smoke.py -v
"""

from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

from tests.test_frontend.playwright_helpers import (
    FIXTURES,
    SCENARIOS_RAW,
    assert_no_ui_failure_copy,
    require_playwright_stack,
    ui_base_url,
    upload_and_analyze,
)

pytestmark = [pytest.mark.live, pytest.mark.playwright]

# Lipids / Healow tricks / infectious etiological / kitchen-sink stress
LIVE_FIXTURES = [
    ("healow_lipids", FIXTURES / "healow_lipid_panel_excerpt.txt", {"Berberine", "Curcumin", "Omega-3"}),
    ("f_prefix_lipids", SCENARIOS_RAW / "format_quest_hdl_ldl_flags.txt", {"Berberine", "Omega-3"}),
    ("h_pylori_etiological", SCENARIOS_RAW / "etiological_h_pylori_urea_breath.txt", {"Mastic Gum", "DGL Licorice"}),
]


@pytest.fixture(scope="module")
def browser_page():
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            resp = page.goto(f"{base}/report.html", wait_until="domcontentloaded", timeout=30_000)
            assert resp and resp.ok, f"UI not reachable at {base}"
            yield page
        finally:
            context.close()
            browser.close()


def test_ui_dom_contract(browser_page):
    """Core report sections and shell exist."""
    for section_id in ("executive-summary", "biological-network", "intervention-library"):
        assert browser_page.locator(f"#{section_id}").count() == 1, section_id
    assert browser_page.locator("#nav-logo .logo").count() == 1
    assert browser_page.locator("#report-empty").count() == 1


@pytest.mark.parametrize("case_id,fixture_path,expected_recs", LIVE_FIXTURES)
def test_ui_upload_to_report(browser_page, case_id: str, fixture_path, expected_recs: set[str]):
    """Upload lab fixture in browser → actionable report without error paragraphs."""
    assert fixture_path.is_file(), fixture_path

    # Fresh guest session per case (avoids stale localStorage from prior uploads).
    browser_page.evaluate("localStorage.clear()")
    browser_page.goto(f"{ui_base_url()}/app.html#upload", wait_until="domcontentloaded")

    upload_and_analyze(browser_page, fixture_path)
    assert_no_ui_failure_copy(browser_page)

    rec_text = browser_page.locator("#intervention-library-body").inner_text()
    matched = {name for name in expected_recs if name in rec_text}
    assert matched, f"{case_id}: expected one of {sorted(expected_recs)} in intervention library; got: {rec_text[:400]}"

    systems_text = browser_page.locator("#biological-network-body").inner_text()
    assert "No biological system data available" not in systems_text, case_id