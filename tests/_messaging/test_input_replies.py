# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from concurrent.futures import Future
from queue import Queue
from threading import Thread
from unittest.mock import Mock

import pytest

from marimo._messaging.cell_output import CellOutput
from marimo._messaging.input import InputReply, deliver_reply
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.streams import ThreadSafeStdin, ThreadSafeStream
from marimo._messaging.types import KernelMessage
from marimo._runtime.execution import ExecutionAttempt
from marimo._types.ids import CellId_t


def test_late_reply_cannot_answer_a_new_prompt() -> None:
    replies: Queue[InputReply] = Queue()
    messages: Queue[KernelMessage] = Queue()
    stream = ThreadSafeStream(
        Mock(send=messages.put), replies, True, CellId_t("cell")
    )
    attempt = ExecutionAttempt(CellId_t("cell"), "input()")
    result: Future[str] = Future()

    def read() -> None:
        with attempt.activate():
            try:
                result.set_result(
                    ThreadSafeStdin(stream)._readline_with_prompt("Empty: ")
                )
            except Exception as error:
                result.set_exception(error)

    reader = Thread(target=read, daemon=True)
    reader.start()
    try:
        notification = deserialize_kernel_message(messages.get(timeout=1))
        assert isinstance(notification, CellNotification)
        assert isinstance(notification.console, CellOutput)
        assert isinstance(notification.console.input_id, str)
        replies.put(InputReply("old-prompt", "stale"))
        replies.put(InputReply(notification.console.input_id, ""))
        assert result.result(timeout=1) == ""
    finally:
        attempt.completed = True
        reader.join(timeout=1)
        stream.stop()
        stream.buffered_console_thread.join(timeout=1)


def test_completed_execution_cannot_request_input() -> None:
    pipe = Mock()
    stream = ThreadSafeStream(pipe, Queue(), False, CellId_t("cell"))
    attempt = ExecutionAttempt(CellId_t("cell"), "input()", completed=True)
    with attempt.activate(), pytest.raises(EOFError, match="has ended"):
        ThreadSafeStdin(stream)._readline_with_prompt("Too late")
    pipe.send.assert_not_called()


def test_a_reply_displaces_one_the_kernel_never_took() -> None:
    replies: Queue[InputReply] = Queue(maxsize=1)
    deliver_reply(replies, InputReply("gone", "stale"))

    deliver_reply(replies, InputReply("waiting", "fresh"))

    assert replies.get_nowait() == InputReply("waiting", "fresh")
    assert replies.empty()


async def test_a_worker_reply_displaces_one_the_kernel_never_took() -> None:
    replies: asyncio.Queue[InputReply] = asyncio.Queue(maxsize=1)
    deliver_reply(replies, InputReply("gone", "stale"))

    deliver_reply(replies, InputReply("waiting", "fresh"))

    assert replies.get_nowait() == InputReply("waiting", "fresh")
    assert replies.empty()
