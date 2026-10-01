# Copyright 2026 Marimo. All rights reserved.
"""Render structured notebook handoffs for Pair CLI users."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from marimo._cli.pair.client import HandoffBatch, display_url

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._messaging.participants import HandoffEvent


def _indented(value: str) -> list[str]:
    return [f"    {line}" for line in value.splitlines()] or ["    "]


def render_handoff(event: HandoffEvent) -> str:
    """Show the cell, failure, and evidence from one human handoff."""
    lines = [
        (
            f"Handoff {event.seq}: the user sent cell {event.cell_id}, "
            f"which raised {event.error}."
        ),
        "Code:",
        *_indented(event.code),
        "Traceback:",
        *_indented(event.traceback),
    ]
    console = [
        (chunk.channel, line)
        for chunk in event.console_tail
        for line in chunk.data.splitlines()
    ][-20:]
    if console:
        channels = {channel for channel, _ in console}
        if len(channels) == 1:
            lines.append(f"Console ({console[0][0]}, last 20 lines):")
            lines.extend(f"    {line}" for _, line in console)
        else:
            lines.append("Console (last 20 lines):")
            lines.extend(
                f"    [{channel}] {line}" for channel, line in console
            )
    if event.note:
        lines.append(f"Note from the user: {event.note}")
    return "\n".join(lines)


def render_batch(
    batch: HandoffBatch,
    *,
    url: str,
    session_id: str,
    token_file: Path | None = None,
) -> dict[str, object]:
    """Render a batch and the command to read events left on the server."""
    result: dict[str, object] = {
        "events": [
            {"seq": event.seq, "text": render_handoff(event)}
            for event in batch.events
        ],
        "remaining": batch.remaining,
    }
    if batch.remaining:
        token_option = (
            f" --token-file {shlex.quote(str(token_file))}"
            if token_file is not None
            else ""
        )
        result["next"] = (
            f"Read {batch.remaining} more: marimo pair events "
            f"--url {shlex.quote(display_url(url))} "
            f"--session {shlex.quote(session_id)}{token_option}"
        )
    return result
