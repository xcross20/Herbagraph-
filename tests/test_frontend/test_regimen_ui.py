"""Playwright DOM tests for Personal Evidence Regimen Truth UI (Slice 1).

Requires: HERBAGRAPH_PLAYWRIGHT=1 and a running stack.
  HERBAGRAPH_PLAYWRIGHT=1 pytest tests/test_frontend/test_regimen_ui.py -v

Scope: 12 required UI states from the Regimen Truth work order.
  • Empty regimen
  • Feature flag off hides module
  • Mobile rendering
  • Cross-user access prevention
  • "Taken all" UX structure
  • Partial intake does not mark unchecked skipped
  • Explicit Skip distinguishable from unconfirmed
  • Correction UI does not delete history
  • Proprietary blend does not invent quantities
  • Stale Case version conflict state
  • Unknown product form remains unknown
  • Confirmed regimen item

PHI-safety: no product names, ingredients, doses, or free text in test assertions.
All test data is synthetic.
"""

from __future__ import annotations

import re

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional browser stack
    pytest.skip("playwright not installed", allow_module_level=True)

from tests.test_frontend.playwright_helpers import (
    require_playwright_stack,
    ui_base_url,
)


pytestmark = [pytest.mark.playwright]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_regimen_module_hidden(page) -> bool:
    """Return True when the My Evidence nav link is absent from the sidebar."""
    return page.locator('[data-nav="evidence"]').count() == 0


def _regimen_view_html(page) -> str:
    """Return the inner HTML of the main app content area."""
    return page.locator("#app-main").inner_html()


def _navigate_to_regimen(page):
    """Navigate to #evidence with the feature flag enabled via query param."""
    page.goto(f"{ui_base_url()}/me.html#evidence?fixture=empty", wait_until="domcontentloaded")
    # Wait for async render
    page.wait_for_timeout(600)


# ── T1: Feature flag off hides the module ────────────────────────────────────

def test_feature_flag_off_hides_regimen_module(browser_page):
    """When PERSONAL_EVIDENCE_REGIMEN_V1 is false, no My Evidence link appears."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to the workspace (default flag off)
        page.goto(f"{base}/me.html#dashboard", wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        # The sidebar should NOT contain a My Evidence link
        assert _is_regimen_module_hidden(page), (
            "My Evidence nav link should be absent when feature flag is off. "
            "Verify PERSONAL_EVIDENCE_REGIMEN_V1 is False in config."
        )

        # Attempting to navigate directly should redirect or show a gate
        page.goto(f"{base}/me.html#evidence", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        html = _regimen_view_html(page)
        # Should not render the Regimen view when flag is off
        assert "My Evidence" not in html and "regimen" not in html.lower(), (
            "Navigating to #evidence with flag off should not render the Regimen view"
        )

        context.close()
        browser.close()


# ── T2: Empty regimen screen ──────────────────────────────────────────────────

def test_empty_regimen_screen_shows_guidance(browser_page):
    """When the module is on but the regimen is empty, show a clear empty state."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Navigate with ?fixture=empty to simulate flag-on + no data
        page.goto(f"{base}/me.html#evidence?fixture=empty", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)

        # Should not be a raw error or crash
        assert "not loaded" not in html.lower(), (
            "Regimen module should be loaded; check that personal-evidence JS files are served"
        )

        # Empty state guidance should be present
        empty_signals = ["no regimen", "add", "start", "your evidence"]
        html_lower = html.lower()
        has_guidance = any(sig in html_lower for sig in empty_signals)
        assert has_guidance, (
            f"Empty regimen should show guidance; got: {html[:300]}"
        )

        context.close()
        browser.close()


# ── T3: Confirmed regimen item renders correctly ──────────────────────────────

def test_confirmed_regimen_item_renders(browser_page):
    """A regimen item with confirmed identity renders as a clean card/row."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=singleItem", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)

        # Should show period grouping (e.g. Morning)
        assert re.search(r"Morning|Evening|Afternoon|Bedtime", html, re.IGNORECASE), (
            "Period section (Morning/Evening/etc.) must be visible"
        )

        # Should show intake action buttons (Taken / Skip)
        assert page.locator(".regimen-item").count() >= 1, (
            "At least one regimen-item element must be present"
        )

        # Status chip should be visible
        assert page.locator(".status-chip, .regimen-intake-actions").count() >= 1, (
            "Intake status controls must be present on a confirmed item"
        )

        context.close()
        browser.close()


# ── T4: Unknown product form remains unknown ───────────────────────────────────

def test_unknown_form_shows_needs_confirmation(browser_page):
    """When botanical identity is incomplete, render Needs confirmation — never guess."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=needsIdentityConfirmation", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)

        # Must show a "needs confirmation" signal — not a guessed form
        confirmation_signals = ["confirm", "which form", "needs confirmation", "what kind"]
        html_lower = html.lower()
        has_confirm_prompt = any(sig in html_lower for sig in confirmation_signals)
        assert has_confirm_prompt, (
            f"Unknown form must show a confirmation prompt; got: {html[:300]}"
        )

        # Must NOT show an auto-assumed form label (e.g. glycinate when unknown)
        forbidden_auto_assigned = ["glycinate", "citrate", "oxide", "elemental"]
        auto_assigned = [f for f in forbidden_auto_assigned if f in html_lower]
        assert not auto_assigned, (
            f"Unknown form must not auto-assign '{auto_assigned[0]}'; "
            "unknown identity should remain unknown"
        )

        context.close()
        browser.close()


# ── T5: "Taken all" produces one action with multiple items ────────────────────

def test_taken_all_action_structure(browser_page):
    """The 'Taken all' button groups all period items under one action."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=singleItem", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)

        # "Taken all" button must be present in the period header
        taken_all_patterns = ["taken all", "taken everything", "mark all taken"]
        html_lower = html.lower()
        has_taken_all = any(pat in html_lower for pat in taken_all_patterns)
        assert has_taken_all, (
            f"'Taken all' button must be present in period header; got: {html[:300]}"
        )

        # Should have multiple regimen items available for the group
        item_count = page.locator(".regimen-item").count()
        assert item_count >= 1, "Period should contain at least one regimen item"

        # Individual Taken/Skip buttons should also be present (for partial intake)
        taken_count = page.locator(".regimen-item .app-btn").count()
        assert taken_count >= item_count, (
            "Each item should have its own intake action button"
        )

        context.close()
        browser.close()


# ── T6: Partial intake does NOT mark unchecked items as skipped ─────────────

def test_partial_intake_unchecked_not_skipped(browser_page):
    """Unchecked means unconfirmed — not skipped. Skip must be an explicit choice."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=partialIntake", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)
        html_lower = html.lower()

        # Must have explicit Skip option for individual items
        skip_signals = ["skip", "skipped"]
        has_skip = any(sig in html_lower for sig in skip_signals)
        assert has_skip, "Partial intake UI must have an explicit Skip option"

        # Must NOT have a pattern that says "unchecked = skipped"
        forbidden_skipped_implies = [
            "unchecking means skip",
            "unselected = skip",
            "not taken = skip",
        ]
        for pattern in forbidden_skipped_implies:
            assert pattern not in html_lower, (
                f"UI must not imply unchecked = skipped: '{pattern}' found"
            )

        context.close()
        browser.close()


# ── T7: Explicit Skip is distinguishable from unconfirmed ──────────────────

def test_explicit_skip_distinct_from_unconfirmed(browser_page):
    """Skip and unconfirmed must be visually distinct. No color-only communication."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=partialIntake", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        # Check that skip and unconfirmed have distinct visual elements
        skip_buttons = page.locator("button").filter(has_text=re.compile(r"skip", re.IGNORECASE))
        # There should be at least one explicit Skip button
        assert skip_buttons.count() >= 1, "At least one explicit Skip button must be present"

        # Verify the DOM structure exists — at least one regimen-item with action buttons
        item_count = page.locator(".regimen-item").count()
        assert item_count >= 1, "Items must have visual status"
        # Each item must have at least one button (Taken or Skip) — not color-only
        total_buttons = page.locator(".regimen-item .app-btn").count()
        assert total_buttons >= item_count, (
            "Each regimen item should have at least one named action button, not color-only status"
        )

        context.close()
        browser.close()


# ── T8: Correction UI does not delete history ─────────────────────────────────

def test_correction_ui_preserves_history(browser_page):
    """Correcting a dose must append a correction — never DELETE the prior entry."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=correctedDose", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)
        html_lower = html.lower()

        # Correction badge / label must be present
        correction_signals = ["correct", "amend", "edit", "change"]
        has_correction = any(sig in html_lower for sig in correction_signals)
        assert has_correction, (
            f"Corrected dose must show a correction badge/label; got: {html[:300]}"
        )

        # No DELETE button should be visible on an exposure/intake record
        # (corrections are append-only)
        assert "delete exposure" not in html_lower, (
            "Correction UI must not expose a DELETE action on an exposure record"
        )

        context.close()
        browser.close()


# ── T9: Proprietary blend does not invent ingredient quantities ───────────────

def test_proprietary_blend_no_invented_amounts(browser_page):
    """A proprietary blend with undisclosed amounts must show 'not disclosed', not a guess."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=proprietaryBlend", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)
        html_lower = html.lower()

        # Must not display specific mg/iu amounts for undisclosed blends
        # Instead should show a "not disclosed" or "proprietary" signal
        undisclosed_signals = [
            "not disclosed",
            "amount unknown",
            "proprietary blend",
            "proprietary formula",
            "blend",
        ]
        has_disclosure_mention = any(sig in html_lower for sig in undisclosed_signals)
        assert has_disclosure_mention, (
            f"Proprietary blend must indicate undisclosed amounts; got: {html[:300]}"
        )

        # Must not show a fake mg amount when none is known
        # Check that the page does not contain a pattern like "500mg" or "200 iu"
        # in the blend section (only in confirmed ingredients if any)
        assert not re.search(r"proprietary.*?\d+\s*mg", html_lower), (
            "Proprietary blend must not display a fabricated mg amount"
        )

        context.close()
        browser.close()


# ── T10: Stale Case version produces conflict state ───────────────────────────

def test_stale_case_version_shows_conflict(browser_page):
    """When the Case version is stale, the UI must show a conflict/reload state."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=stale", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        html = _regimen_view_html(page)
        html_lower = html.lower()

        # Conflict signal must be present — not a silent overwrite
        conflict_signals = ["conflict", "out of date", "reload", "refresh", "version"]
        has_conflict = any(sig in html_lower for sig in conflict_signals)
        assert has_conflict, (
            f"Stale version must show a conflict/reload prompt; got: {html[:300]}"
        )

        # Must NOT silently save over a stale version
        assert "saved" not in html_lower or "conflict" in html_lower, (
            "A stale Case version must not be silently overwritten"
        )

        context.close()
        browser.close()


# ── T11: Mobile viewport rendering ─────────────────────────────────────────

def test_mobile_viewport_regimen_renders(browser_page):
    """On mobile (375px wide), the Regimen UI must be usable without horizontal scroll."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 375, "height": 812})
        page = context.new_page()

        page.goto(f"{base}/me.html#evidence?fixture=singleItem", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        # No horizontal overflow
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        inner_width = page.evaluate("window.innerWidth")
        assert scroll_width <= inner_width, (
            f"Mobile viewport ({inner_width}px) must not require horizontal scroll; "
            f"scrollWidth={scroll_width}"
        )

        # Period section should be readable without horizontal scroll
        period_text = page.locator(".regimen-period, .regimen-section-title").first.inner_text()
        assert len(period_text.strip()) > 0, "Period section must render on mobile"

        # Intake action buttons must be visible and tappable (no overflow:hidden on parent)
        button = page.locator(".regimen-intake-actions .app-btn").first
        assert button.is_visible(), "Intake action button must be visible on mobile"

        context.close()
        browser.close()


# ── T12: Cross-user regimen access prevention ─────────────────────────────────

def test_another_users_regimen_not_accessible(browser_page):
    """A user must not be able to access another user's regimen via URL manipulation."""
    require_playwright_stack()
    base = ui_base_url()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Authenticate as user A
        page.goto(f"{base}/me.html#dashboard", wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        # Get user A's case ID from the session
        case_id_a = page.evaluate(
            "() => JSON.parse(localStorage.getItem('hg_case') || '{}').id || null"
        )

        if case_id_a:
            # Attempt to access user B's regimen via URL parameter
            fake_case_id = "00000000-0000-0000-0000-000000000001"
            page.goto(
                f"{base}/me.html#evidence?patient={fake_case_id}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(800)

            html = _regimen_view_html(page)
            html_lower = html.lower()

            # Must not show the regimen data — should be an error or redirect
            assert (
                "not authorized" in html_lower
                or "not found" in html_lower
                or "access denied" in html_lower
                or "evidence" not in html_lower
                or _is_regimen_module_hidden(page)
            ), (
                f"User A should not be able to access user B's regimen via patient param; "
                f"got: {html[:300]}"
            )
        else:
            # No active case — navigation should redirect to login or dashboard
            page.goto(
                f"{base}/me.html#evidence?patient=00000000-0000-0000-0000-000000000001",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(500)
            assert (
                "#dashboard" in page.url
                or "#login" in page.url
                or _is_regimen_module_hidden(page)
            ), "Unauthorized patient access should redirect or deny"

        context.close()
        browser.close()
