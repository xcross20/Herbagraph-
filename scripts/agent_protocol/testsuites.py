"""Map Architect required-check text and changed paths to repository-owned suites."""

from __future__ import annotations

from .constants import APPROVED_TEST_SUITES, PATH_SUITE_PREFIXES


def mapped_test_commands(required_checks: tuple[str, ...] | list[str]) -> list[tuple[str, ...]]:
    commands = [APPROVED_TEST_SUITES["protocol"]]
    seen = {"protocol"}
    for raw in required_checks:
        text = (raw or "").lower()
        for key, command in APPROVED_TEST_SUITES.items():
            if key in seen:
                continue
            if key in text or " ".join(command).lower() in text:
                commands.append(command)
                seen.add(key)
    return commands


def suites_for_changed_paths(paths: list[str]) -> list[tuple[str, ...]]:
    keys: set[str] = set()
    for path in paths:
        rel = (path or "").replace("\\", "/").lstrip("./")
        for prefix, key in PATH_SUITE_PREFIXES:
            if rel == prefix.rstrip("/") or rel.startswith(prefix):
                keys.add(key)
    if not keys:
        keys.add("gates")
    if "protocol" not in keys and any(
        rel.startswith("scripts/agent_protocol/") or rel.startswith("tests/test_agent_protocol/")
        for rel in ((path or "").replace("\\", "/") for path in paths)
    ):
        keys.add("protocol")
    ordered = []
    for key in ("protocol", "api", "core", "app", "frontend", "gates"):
        if key in keys and key in APPROVED_TEST_SUITES:
            ordered.append(APPROVED_TEST_SUITES[key])
    return ordered or [APPROVED_TEST_SUITES["protocol"]]


def is_allowlisted_command(command: tuple[str, ...] | list[str]) -> bool:
    return tuple(command) in APPROVED_TEST_SUITES.values()
