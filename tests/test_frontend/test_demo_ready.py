"""The personal demo leads with typed labs and a stack check."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = (ROOT / "frontend" / "js" / "workspace-app.js").read_text(encoding="utf-8")
ME = (ROOT / "frontend" / "me.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "landing.css").read_text(encoding="utf-8")


def test_personal_home_offers_typed_labs_and_stack_check():
    cards = JS.split("function renderPersonalLaunchCards")[1].split("function renderPersonalDashboard")[0]
    dash = JS.split("function renderPersonalDashboard")[1].split("async function renderDashboard")[0]
    assert "renderPersonalLaunchCards()" in dash
    assert "Type lab values" in cards
    assert 'href="/stack.html"' in cards
    assert "Upload my labs" not in dash
    assert "Existing workflow" not in dash
    assert "Personal portal" in dash
    assert "not a new product" not in dash
    assert "Suggestions from a conversation show up here." in dash


def test_personal_command_bar_has_no_new_patient():
    bar = JS.split("function commandBar")[1].split("async function backgroundQueueDown")[0]
    personal = bar.split("if (!isClinicianWorkspace())")[1].split("return `")[1]
    assert "Type lab values" in personal
    assert "/stack.html" in personal
    assert "New patient" not in personal
    assert "+ New patient" in bar


def test_file_and_analysis_stop_when_the_queue_is_down():
    assert "redis_reachable === false" in JS
    assert "File reading is paused. Type the values instead." in JS
    assert "Analysis is paused. A stack check still uses the labs you typed." in JS


def test_guest_sidebar_does_not_show_the_generated_address():
    label = JS.split("function accountLabel")[1].split("function isClinicianWorkspace")[0]
    assert "@guest.herbagraph-app.io" in label
    assert "Guest · ${role}" in label


def test_personal_mobile_action_types_labs():
    assert 'href="#upload?mode=manual"' in ME
    assert 'aria-label="Type lab values"' in ME


def test_stack_action_is_green_on_the_light_page():
    rule = CSS.split(".landing-page .app-main .landing-btn-primary {")[1].split("}")[0]
    assert "#2e7d57" in rule
    assert "color: #fff" in rule


def test_short_laptop_screen_keeps_the_doors_in_play():
    rule = CSS.split("@media (max-height: 980px) and (min-width: 900px)")[1].split("}")[0]
    assert ".landing-hero" in rule
    assert "min-height: 0" in rule
