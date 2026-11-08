# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from queue import Queue
from unittest.mock import Mock

import pytest

from marimo._messaging.cell_output import CellOutput
from marimo._messaging.input import InputReply
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.streams import ThreadSafeStdin, ThreadSafeStream
from marimo._messaging.types import KernelMessage
from marimo._runtime.execution import ExecutionAttempt
from marimo._types.ids import CellId_t


def test_late_reply_cannot_answer_a_new_prompt() -> None:
    replies: Queue[str | InputReply] = Queue()

    def answer(message: KernelMessage) -> None:
        notification = deserialize_kernel_message(message)
        assert isinstance(notification, CellNotification)
        assert isinstance(notification.console, CellOutput)
        assert isinstance(notification.console.input_id, str)
        replies.put(InputReply("old-prompt", "stale"))
        replies.put(InputReply(notification.console.input_id, ""))

    stream = ThreadSafeStream(
        Mock(send=answer), replies, True, CellId_t("cell")
    )
    try:
        assert ThreadSafeStdin(stream)._readline_with_prompt("Empty: ") == ""
    finally:
        stream.stop()
        stream.buffered_console_thread.join(timeout=1)


def test_completed_execution_cannot_request_input() -> None:
    pipe = Mock()
    stream = ThreadSafeStream(pipe, Queue(), False, CellId_t("cell"))
    attempt = ExecutionAttempt(CellId_t("cell"), "input()", completed=True)
    with attempt.activate(), pytest.raises(EOFError, match="has ended"):
        ThreadSafeStdin(stream)._readline_with_prompt("Too late")
    pipe.send.assert_not_called()
