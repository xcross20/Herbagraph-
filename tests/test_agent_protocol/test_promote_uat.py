from agent_protocol.promote_uat import (
    classify_changed_paths,
    merge_into_integration_agent,
    promote_is_safe,
)

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_only_canary_fixture_is_autonomous_uat():
    ok = classify_changed_paths(["tests/fixtures/agent_loop_canary.txt"])
    assert ok.allowed is True
    assert ok.reason == "autonomous_uat_allowlist"
    blocked = classify_changed_paths(["tests/fixtures/agent_loop_canary.txt", "app/main.py"])
    assert blocked.allowed is False
    assert "app/main.py" in blocked.reason


def test_promote_rejects_main_and_stale_head():
    assert promote_is_safe(
        base_ref="main",
        head_ref="grok/7-x",
        live_head_sha=SHA,
        reviewed_sha=SHA,
        paths=["tests/fixtures/agent_loop_canary.txt"],
    ).reason == "base_is_production_or_main"
    assert promote_is_safe(
        base_ref="integration/agent",
        head_ref="grok/7-x",
        live_head_sha=OTHER,
        reviewed_sha=SHA,
        paths=["tests/fixtures/agent_loop_canary.txt"],
    ).reason == "stale_run_remote_head_changed"


def test_merge_helper_is_sha_locked_and_skips_non_allowlisted_prs():
    calls = []

    def request(method, url, token, payload=None):
        calls.append((method, url, payload))
        if method == "GET" and url.endswith("/pulls/15"):
            return {
                "base": {"ref": "integration/agent"},
                "head": {"ref": "grok/7-loop-canary", "sha": SHA},
            }
        if method == "GET" and "/files" in url:
            return [{"filename": "app/main.py"}]
        raise AssertionError((method, url))

    result = merge_into_integration_agent(
        api_root="https://api.github.com/repos/o/r",
        token="t",
        pr_number=15,
        head_sha=SHA,
        title="merge(uat): no",
        request=request,
    )
    assert result["merged"] is False
    assert any(method == "GET" for method, _, _ in calls)
    assert all(method != "PUT" for method, _, _ in calls)


def test_merge_helper_puts_only_when_allowlisted():
    calls = []

    def request(method, url, token, payload=None):
        calls.append((method, url, payload))
        if method == "GET" and url.endswith("/pulls/15"):
            return {
                "base": {"ref": "integration/agent"},
                "head": {"ref": "grok/7-loop-canary", "sha": SHA},
            }
        if method == "GET" and "/files" in url:
            return [{"filename": "tests/fixtures/agent_loop_canary.txt"}]
        if method == "PUT" and url.endswith("/merge"):
            assert payload["sha"] == SHA
            assert payload["merge_method"] == "merge"
            return {"merged": True}
        raise AssertionError((method, url))

    result = merge_into_integration_agent(
        api_root="https://api.github.com/repos/o/r",
        token="t",
        pr_number=15,
        head_sha=SHA,
        title="merge(uat): HG-7",
        request=request,
    )
    assert result["merged"] is True
    assert any(method == "PUT" for method, _, _ in calls)
