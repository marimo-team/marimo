# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import multiprocessing as mp
import os
import queue
import sys
import threading
from collections import deque
from multiprocessing.connection import Connection
from typing import Any, Iterable, Optional

from marimo import _loggers
from marimo._ast.cell import CellId_t
from marimo._messaging.console_output_worker import ConsoleMsg, buffered_writer

LOGGER = _loggers.marimo_logger()

# Byte limits on outputs. Limits exist for two reasons:
#
# 1. We use a multiprocessing.Connection object to send outputs from
#    the kernel to the server (the server then sends the output to
#    the frontend via a websocket). The Connection object has a limit
#    of ~32MiB that it can send before it chokes
#    (https://docs.python.org/3/library/multiprocessing.html#multiprocessing.connection.Connection.send).
#
#    TODO(akshayka): Get around this by breaking up the message sent
#    over the Connection or plumbing the websocket into the kernel.
#
# 2. The frontend chokes when we send outputs that are too big, i.e.
#    it freezes and sometimes even crashes. That can lead to lost work.
#    It appears this is the bottleneck right now, compared to 1.
#
# Usually users only output gigantic things accidentally, so refusing
# to show large outputs should in most cases not bother the user too much.
# In any case, it's better than breaking the frontend/kernel.
#
# Output not shown if larger than OUTPUT_MAX_BYTES=5MB
OUTPUT_MAX_BYTES = int(os.getenv("MARIMO_OUTPUT_MAX_BYTES", 5_000_000))

# Standard stream truncated if larger than STD_STREAM_MAX_BYTES=1MB
STD_STREAM_MAX_BYTES = int(os.getenv("MARIMO_STD_STREAM_MAX_BYTES", 1_000_000))


class Stream:
    """A thread-safe wrapper around a pipe."""

    def __init__(
        self,
        pipe: Connection,
        input_queue: mp.Queue[str] | queue.Queue[str],
        cell_id: Optional[CellId_t] = None,
    ):
        self.pipe = pipe
        self.cell_id = cell_id
        # A single stream is shared by the kernel and the code completion
        # worker. The lock should almost always be uncontended.
        self.stream_lock = threading.Lock()

        # Console outputs are buffered
        self.console_msg_cv = threading.Condition(threading.Lock())
        self.console_msg_queue: deque[ConsoleMsg] = deque()
        self.buffered_console_thread = threading.Thread(
            target=buffered_writer,
            args=(self.console_msg_queue, self, self.console_msg_cv),
        )
        self.buffered_console_thread.start()

        # stdin messages are pulled from this queue
        self.input_queue = input_queue

    def write(self, op: str, data: dict[Any, Any]) -> None:
        with self.stream_lock:
            try:
                self.pipe.send((op, data))
            except OSError as e:
                # Most likely a BrokenPipeError, caused by the
                # server process shutting down
                LOGGER.debug("Error when writing (op: %s) to pipe: %s", op, e)


class Stdout(io.TextIOBase):
    name = "stdout"

    def __init__(self, stream: Stream):
        self.stream = stream

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        # TODO(akshayka): maybe force the buffered writer to write
        return

    def write(self, data: str) -> int:
        assert self.stream.cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                "write() argument must be a str, not %s" % type(data).__name__
            )
        if sys.getsizeof(data) > STD_STREAM_MAX_BYTES:
            sys.stderr.write(
                "Warning: marimo truncated a very large console output.\n"
            )
            data = data[: int(STD_STREAM_MAX_BYTES)] + " ... "
        self.stream.console_msg_queue.append(
            ConsoleMsg(stream="stdout", cell_id=self.stream.cell_id, data=data)
        )
        with self.stream.console_msg_cv:
            self.stream.console_msg_cv.notify()
        return len(data)

    # Buffer type not available python < 3.12, hence type ignore
    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override] # noqa: E501
        for line in sequence:
            self.write(line)


class Stderr(io.TextIOBase):
    name = "stderr"

    def __init__(self, stream: Stream):
        self.stream = stream

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        # TODO(akshayka): maybe force the buffered writer to write
        return

    def write(self, data: str) -> int:
        assert self.stream.cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                "write() argument must be a str, not %s" % type(data).__name__
            )
        if sys.getsizeof(data) > STD_STREAM_MAX_BYTES:
            data = (
                "Warning: marimo truncated a very large console output.\n"
                + data[: int(STD_STREAM_MAX_BYTES)]
                + " ... "
            )

        with self.stream.console_msg_cv:
            self.stream.console_msg_queue.append(
                ConsoleMsg(
                    stream="stderr", cell_id=self.stream.cell_id, data=data
                )
            )
            self.stream.console_msg_cv.notify()
        return len(data)

    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override] # noqa: E501
        for line in sequence:
            self.write(line)


class Stdin(io.TextIOBase):
    """Implements a subset of stdin."""

    name = "stdin"

    def __init__(self, stream: Stream):
        self.stream = stream

    def writable(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def _readline_with_prompt(self, prompt: str = "") -> str:
        """Read input from the standard in stream, with an optional prompt."""
        assert self.stream.cell_id is not None
        if not isinstance(prompt, str):
            raise TypeError(
                "prompt must be a str, not %s" % type(prompt).__name__
            )
        if sys.getsizeof(prompt) > STD_STREAM_MAX_BYTES:
            prompt = (
                "Warning: marimo truncated a very large console output.\n"
                + prompt[: int(STD_STREAM_MAX_BYTES)]
                + " ... "
            )

        with self.stream.console_msg_cv:
            # This sends a prompt request to the frontend.
            self.stream.console_msg_queue.append(
                ConsoleMsg(
                    stream="stdin", cell_id=self.stream.cell_id, data=prompt
                )
            )
            self.stream.console_msg_cv.notify()

        return self.stream.input_queue.get()

    def readline(self, size: int | None = -1) -> str:  # type: ignore[override]  # noqa: E501
        # size only included for compatibility with sys.stdin.readline API;
        # we don't support it.
        del size
        return self._readline_with_prompt(prompt="")

    def readlines(self, hint: int | None = -1) -> list[str]:  # type: ignore[override]  # noqa: E501
        # Just an alias for readline.
        #
        # hint only included for compatibility with sys.stdin.readlines API;
        # we don't support it.
        del hint
        return self._readline_with_prompt(prompt="").split("\n")
