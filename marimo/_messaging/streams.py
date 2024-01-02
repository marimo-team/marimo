# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
import threading
from collections import deque
from multiprocessing.connection import Connection
from typing import Any, Optional

from marimo import _loggers
from marimo._ast.cell import CellId_t
from marimo._messaging.console_output_worker import ConsoleMsg, buffered_writer
from marimo._runtime.context import get_context

LOGGER = _loggers.marimo_logger()


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
            try:
                self.pipe.send((op, data))
            except OSError as e:
                # Most likely a BrokenPipeError, caused by the
                # server process shutting down
                LOGGER.debug("Error when writing (op: %s) to pipe: %s", op, e)


class Stdout:
    def __init__(self, stream: Stream):
        self.stream = stream

    def write(self, data: str) -> None:
        assert self.stream.cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                "write() argument must be a str, not %s" % type(data).__name__
            )
        max_bytes = get_context().std_stream_max_size_bytes
        if sys.getsizeof(data) > max_bytes:
            sys.stderr.write(
                "Warning: marimo truncated a very large console output.\n"
            )
            data = data[: int(max_bytes)] + " ... "
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
        max_bytes = get_context().std_stream_max_size_bytes
        if not isinstance(data, str):
            raise TypeError(
                "write() argument must be a str, not %s" % type(data).__name__
            )
        if sys.getsizeof(data) > max_bytes:
            data = (
                "Warning: marimo truncated a very large console output.\n"
                + data[: int(max_bytes)]
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
