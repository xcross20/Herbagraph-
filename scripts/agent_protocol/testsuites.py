"""Map Architect required-check text to repository-owned pytest suites."""

from __future__ import annotations

from .constants import APPROVED_TEST_SUITES


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


def is_allowlisted_command(command: tuple[str, ...] | list[str]) -> bool:
    return tuple(command) in APPROVED_TEST_SUITES.values()
