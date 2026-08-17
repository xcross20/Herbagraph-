from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "agent_loop_canary.txt"


def test_canary_fixture_is_absent_or_ready():
    if not FIXTURE.is_file():
        return
    assert FIXTURE.read_text(encoding="utf-8") == "canary-ready\n"
