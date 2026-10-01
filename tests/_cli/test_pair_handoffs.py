# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Any

from marimo._cli.pair.client import HandoffBatch
from marimo._cli.pair.handoffs import render_batch, render_handoff
from marimo._messaging.participants import HandoffConsoleOutput, HandoffEvent


def _event(**overrides: object) -> HandoffEvent:
    values: dict[str, Any] = {
        "seq": 42,
        "created_at": 0.0,
        "cell_id": "AbCd",
        "error": "NameError: name 'df' is not defined",
        "code": "df.head()",
        "traceback": "Traceback (most recent call last):\nNameError",
        "console_tail": (
            HandoffConsoleOutput(channel="stderr", data="first\nsecond\n"),
        ),
        "note": "check the import above",
    }
    values.update(overrides)
    return HandoffEvent(**values)


def test_render_handoff_keeps_context_and_optional_note() -> None:
    assert render_handoff(_event()) == (
        "Handoff 42: the user sent cell AbCd, which raised "
        "NameError: name 'df' is not defined.\n"
        "Code:\n"
        "    df.head()\n"
        "Traceback:\n"
        "    Traceback (most recent call last):\n"
        "    NameError\n"
        "Console (stderr, last 20 lines):\n"
        "    first\n"
        "    second\n"
        "Note from the user: check the import above"
    )


def test_render_handoff_limits_console_to_last_twenty_lines() -> None:
    event = _event(
        console_tail=(
            HandoffConsoleOutput(
                channel="stdout", data="\n".join(str(n) for n in range(25))
            ),
        ),
        note=None,
    )
    rendered = render_handoff(event)

    assert "Console (stdout, last 20 lines):\n    5\n" in rendered
    assert "    24" in rendered
    assert "    4\n" not in rendered
    assert "Note from the user" not in rendered


def test_render_batch_adds_read_command_for_remaining_events() -> None:
    rendered = render_batch(
        HandoffBatch(events=(_event(),), remaining=2),
        url="https://example.com?token=private",
        session_id="session-1",
    )

    assert rendered["events"][0]["seq"] == 42
    assert rendered["remaining"] == 2
    assert rendered["next"] == (
        "Read 2 more: marimo pair events --url https://example.com "
        "--session session-1"
    )

    with_token_file = render_batch(
        HandoffBatch(events=(), remaining=1),
        url="https://example.com",
        session_id="session-1",
        token_file=Path("my token.txt"),
    )
    assert with_token_file["next"] == (
        "Read 1 more: marimo pair events --url https://example.com "
        "--session session-1 --token-file 'my token.txt'"
    )
