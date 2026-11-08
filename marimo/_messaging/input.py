# Copyright 2026 Marimo. All rights reserved.
"""Replies addressed to a kernel input prompt."""

from __future__ import annotations

import msgspec

from marimo._messaging.context import EXECUTION_CTX


class InputReply(msgspec.Struct, frozen=True):
    input_id: str
    value: str


def require_active_execution() -> None:
    execution = EXECUTION_CTX.get()
    if (
        execution is not None
        and execution.attempt is not None
        and execution.attempt.completed
    ):
        raise EOFError("The execution requesting input has ended")
