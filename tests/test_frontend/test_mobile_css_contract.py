"""Contract tests for mobile-responsive workspace CSS."""

from pathlib import Path

_APP_CSS = Path(__file__).resolve().parents[2] / "frontend" / "css" / "app.css"
_REPORT_CSS = Path(__file__).resolve().parents[2] / "frontend" / "css" / "report.css"


def test_app_css_has_mobile_drawer_styles():
    css = _APP_CSS.read_text(encoding="utf-8")
    assert "@media (max-width: 900px)" in css
    assert ".mobile-topbar" in css
    assert ".app-sidebar.is-open" in css
    assert ".sidebar-backdrop" in css
    assert ".sidebar-backdrop.is-visible" in css
    assert "translateX" in css
    assert "env(safe-area-inset-top)" in css
    assert "100dvh" in css or "100vh" in css
    # Backdrop default must not paint a permanent gray veil
    assert "pointer-events: none" in css


def test_report_css_has_mobile_breakpoints():
    css = _REPORT_CSS.read_text(encoding="utf-8")
    assert "@media (max-width: 960px)" in css
    assert "safe-area-inset" in css
    assert "-webkit-overflow-scrolling: touch" in css
