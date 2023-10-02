# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
import threading
from collections import deque
from multiprocessing.connection import Connection
from typing import Any, Optional

from marimo._ast.cell import CellId_t
from marimo._messaging.console_output_worker import ConsoleMsg, buffered_writer

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
OUTPUT_MAX_BYTES = 5_000_000

# Standard stream truncated if larger than STD_STREAM_MAX_BYTES=1MB
STD_STREAM_MAX_BYTES = 1_000_000


class Stream:
    """A thread-safe wrapper around a pipe."""

    def __init__(self, pipe: Connection, cell_id: Optional[CellId_t] = None):
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

    def write(self, op: str, data: dict[Any, Any]) -> None:
        with self.stream_lock:
            self.pipe.send((op, data))


class Stdout:
    def __init__(self, stream: Stream):
        self.stream = stream

    def write(self, data: str) -> None:
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

    def flush(self) -> None:
        # TODO(akshayka): maybe force the buffered writer to write
        return

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False


class Stderr:
    def __init__(self, stream: Stream):
        self.stream = stream

    def write(self, data: str) -> None:
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

    def flush(self) -> None:
        return

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False
