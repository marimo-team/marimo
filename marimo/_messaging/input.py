# Copyright 2026 Marimo. All rights reserved.
"""Replies addressed to a kernel input prompt."""

from __future__ import annotations

import asyncio
import contextlib
import queue
from typing import Protocol

import msgspec

from marimo._messaging.context import EXECUTION_CTX


class InputReply(msgspec.Struct, frozen=True):
    input_id: str
    value: str


class ReplyQueue(Protocol):
    def put_nowait(self, item: InputReply) -> None: ...

    def get_nowait(self) -> InputReply: ...


def deliver_reply(replies: ReplyQueue, reply: InputReply) -> None:
    """Queue `reply` for the kernel, displacing one the kernel never took.

    The queue holds a single reply, and only one prompt waits for input at
    a time. So a reply still queued when another arrives was meant for a
    prompt whose reader has gone, as when its cell was interrupted before
    the kernel read the answer. Keeping it would leave no room for the
    reply the kernel is waiting for now.
    """
    try:
        replies.put_nowait(reply)
    except (queue.Full, asyncio.QueueFull):
        with contextlib.suppress(queue.Empty, asyncio.QueueEmpty):
            replies.get_nowait()
        replies.put_nowait(reply)


def require_active_execution() -> None:
    execution = EXECUTION_CTX.get()
    if (
        execution is not None
        and execution.attempt is not None
        and execution.attempt.completed
    ):
        raise EOFError("The execution requesting input has ended")
