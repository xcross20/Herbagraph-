"""Contract tests for How It Works methodology page."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "frontend" / "how-it-works.html"
CSS = ROOT / "frontend" / "css" / "how-it-works.css"
JS = ROOT / "frontend" / "js" / "how-it-works.js"


def test_how_it_works_assets_exist():
    assert HTML.is_file()
    assert CSS.is_file()
    assert JS.is_file()


def test_how_it_works_content_contract():
    html = HTML.read_text(encoding="utf-8")
    assert "How HerbaGraph turns labs" in html
    assert "7-stage" in html or "7-stage analysis" in html
    assert "MODULATES" in html
    assert "TARGETS" in html
    assert "CONTAINS" in html
    assert "Legacy catalogs" in html
    assert "Canonical graph" in html
    assert "how-it-works.css" in html
    assert "how-it-works.js" in html
    assert 'name="viewport"' in html


def test_landing_and_app_link_how_it_works():
    landing = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    clinic = (ROOT / "frontend" / "clinic.html").read_text(encoding="utf-8")
    me = (ROOT / "frontend" / "me.html").read_text(encoding="utf-8")
    assert "/how-it-works.html" in landing
    assert "/how-it-works.html" in clinic
    assert "/how-it-works.html" in me


def test_how_it_works_js_has_stages():
    js = JS.read_text(encoding="utf-8")
    assert "Lab parser" in js
    assert "Report assembly" in js
    assert "hiw-tree-chart" in js
