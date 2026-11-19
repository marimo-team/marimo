# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import codecs
import contextlib
import io
import os
import queue
import selectors
import sys
import threading
from collections import deque
from contextvars import Context
from dataclasses import replace
from typing import (
    TYPE_CHECKING,
    Protocol,
)
from uuid import uuid4

from marimo import _loggers
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.console_output_worker import (
    ConsoleMsg,
    FlushMarker,
    buffered_writer,
)
from marimo._messaging.context import EXECUTION_CTX, RUN_ID_CTX
from marimo._messaging.input import InputReply, require_active_execution
from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._messaging.types import (
    KernelMessage,
    Stderr,
    Stdin,
    Stdout,
    Stream,
)
from marimo._session.queue import QueueType
from marimo._types.ids import CellId_t
from marimo._utils.signals import SigintHandler

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

LOGGER = _loggers.marimo_logger()


# Maximum time to block waiting for the buffered console writer to flush.
# The flush hook runs on the hot path between cell execution and idle, so
# we bound the wait even though flushes normally complete in <10ms.
_FLUSH_CONSOLE_TIMEOUT_S = 5.0


# Byte limits on outputs exist for two reasons
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


def output_max_bytes() -> int:
    from marimo._runtime.context import ContextNotInitializedError, get_context

    try:
        return get_context().marimo_config.runtime.output_max_bytes
    except ContextNotInitializedError:
        return 5_000_000  # 5MB


def std_stream_max_bytes() -> int:
    from marimo._runtime.context import ContextNotInitializedError, get_context

    try:
        return get_context().marimo_config.runtime.std_stream_max_bytes
    except ContextNotInitializedError:
        return 1_000_000  # 1MB


class PipeProtocol(Protocol):
    def send(self, obj: KernelMessage) -> None:
        pass


class QueuePipe(PipeProtocol):
    def __init__(self, queue: QueueType[KernelMessage]):
        self._queue = queue

    def send(self, obj: KernelMessage) -> None:
        self._queue.put_nowait(obj)


class ThreadSafeStream(Stream):
    """A thread-safe wrapper around a pipe.

    Does not own the pipe or queue.
    """

    def __init__(
        self,
        pipe: PipeProtocol,
        input_queue: QueueType[InputReply],
        redirect_console: bool,
        cell_id: CellId_t | None = None,
    ):
        self.pipe = pipe
        self.cell_id = cell_id
        self.redirect_console = redirect_console
        # A single stream is shared by the kernel and the code completion
        # worker. The lock should almost always be uncontended.
        self.stream_lock = threading.Lock()

        self._console_stopped = threading.Event()
        if self.redirect_console:
            # Console outputs are buffered
            self.console_msg_cv = threading.Condition(threading.Lock())
            self.console_msg_queue: deque[ConsoleMsg | FlushMarker | None] = (
                deque()
            )
            self.buffered_console_thread = threading.Thread(
                target=buffered_writer,
                args=(self.console_msg_queue, self, self.console_msg_cv),
            )
            self.buffered_console_thread.start()

        # stdin messages are pulled from this queue
        self.input_queue = input_queue
        self.input_lock = threading.Lock()

    def write(self, data: KernelMessage) -> None:
        # The interrupt handler also writes to this stream. Finish the send
        # and release the lock before allowing it to run.
        with SigintHandler.defer(), self.stream_lock:
            try:
                self.pipe.send(data)
            except OSError as e:
                from marimo._messaging.serde import (
                    deserialize_kernel_notification_name,
                )

                # Most likely a BrokenPipeError, caused by the
                # server process shutting down
                LOGGER.debug(
                    "Error when writing (op: %s) to pipe: %s",
                    deserialize_kernel_notification_name(data),
                    e,
                )

    def copy_for_thread(self) -> ThreadSafeStream:
        stream = type(self)(
            pipe=self.pipe,
            input_queue=self.input_queue,
            redirect_console=False,
            cell_id=self.cell_id,
        )
        stream.input_lock = self.input_lock
        # The parent stream and thread copy write to the same pipe. Share the
        # transport lock so pipe.send() remains serialized across both views.
        stream.stream_lock = self.stream_lock
        return stream

    def queue_console(self, message: ConsoleMsg) -> None:
        with self.console_msg_cv:
            if not self._console_stopped.is_set():
                self.console_msg_queue.append(message)
                self.console_msg_cv.notify()

    def flush_console(self) -> None:
        """Force the buffered console writer to flush immediately.

        Blocks until all pending console messages have been sent to the
        frontend, or until a short timeout elapses if the writer thread
        is no longer alive.  This ensures that stderr/stdout output
        produced during cell execution is delivered before the cell is
        marked idle.
        """
        if not self.redirect_console:
            return
        # If the buffered writer isn't alive (e.g., shutdown in progress),
        # enqueuing a marker would never be drained. Bail out early.
        if not self.buffered_console_thread.is_alive():
            return
        marker = FlushMarker()
        with self.console_msg_cv:
            if self._console_stopped.is_set():
                return
            self.console_msg_queue.append(marker)
            self.console_msg_cv.notify()
        # Bounded wait: if the writer dies or stalls, don't block the
        # caller indefinitely.
        if not marker.done.wait(timeout=_FLUSH_CONSOLE_TIMEOUT_S):
            LOGGER.warning(
                "Timed out waiting for console flush after %ss",
                _FLUSH_CONSOLE_TIMEOUT_S,
            )

    def stop(self) -> None:
        """Teardown resources created by the stream."""
        # Sending `None` through the queue signals the console thread to exit.
        # We don't join the thread in case its processing outputs still; don't
        # want to block the entire program.
        self._console_stopped.set()
        if self.redirect_console:
            with self.console_msg_cv:
                self.console_msg_queue.append(None)
                self.console_msg_cv.notify()


def _native_chunks(fd: int, stopped: threading.Event) -> Iterator[bytes]:
    if sys.platform == "win32":
        # Windows selectors only support sockets. Peek before reading so a
        # child holding an idle pipe can't block kernel teardown.
        import _winapi
        import msvcrt

        handle = msvcrt.get_osfhandle(fd)
        while not stopped.is_set():
            try:
                # The last two fields are total bytes and bytes in this message.
                available = _winapi.PeekNamedPipe(handle)[-2]
            except BrokenPipeError:
                return
            if available:
                yield os.read(fd, min(available, 4096))
            else:
                stopped.wait(0.01)
        return

    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while not stopped.is_set():
            if selector.select(timeout=0.1):
                data = os.read(fd, 4096)
                if not data:
                    return
                yield data


def _forward_os_stream(
    standard_stream: ThreadSafeStdout | ThreadSafeStderr,
    read_fd: int,
    cell_id: CellId_t,
) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    with os.fdopen(read_fd, "rb", buffering=0):
        for data in _native_chunks(
            read_fd, standard_stream._stream._console_stopped
        ):
            if text := decoder.decode(data):
                standard_stream._write_with_mimetype(
                    text, "text/plain", cell_id=cell_id
                )
        if tail := decoder.decode(b"", final=True):
            standard_stream._write_with_mimetype(
                tail, "text/plain", cell_id=cell_id
            )


def _flush_native_buffer(stream: ThreadSafeStdout | ThreadSafeStderr) -> None:
    if stream.buffer is not None and not stream.buffer.closed:
        stream.buffer.flush()


# NB: Python doesn't provide a standard out class to inherit from, so
# we inherit from TextIOBase.
class ThreadSafeStdout(Stdout):
    encoding = sys.stdout.encoding
    errors = sys.stdout.errors
    _fileno: int | None = None

    def __init__(
        self, stream: ThreadSafeStream, forward_os_streams: bool = True
    ):
        self._stream = stream
        self._original_fd = sys.stdout.fileno()
        # Expose the underlying binary buffer so that code writing to
        # sys.stdout.buffer (e.g. package installation logging) keeps working.
        self.buffer: io.BufferedIOBase | None = getattr(
            sys.stdout, "buffer", None
        )
        self._forward_os_streams = forward_os_streams

    def fileno(self) -> int:
        if self._fileno is not None:
            return self._fileno
        raise io.UnsupportedOperation("Stream not redirected, no fileno.")

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        _flush_native_buffer(self)
        self._stream.flush_console()

    def _write_with_mimetype(
        self,
        data: str,
        mimetype: ConsoleMimeType,
        *,
        cell_id: CellId_t | None = None,
    ) -> int:
        cell_id = self._stream.cell_id if cell_id is None else cell_id
        assert cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                f"write() argument must be a str, not {type(data).__name__}"
            )
        max_bytes = std_stream_max_bytes()
        if sys.getsizeof(data) > max_bytes:
            sys.stderr.write(
                "Warning: marimo truncated a very large console output.\n"
            )
            data = data[: int(max_bytes)] + " ... "
        self._stream.queue_console(
            ConsoleMsg(
                stream=CellChannel.STDOUT,
                cell_id=cell_id,
                data=data,
                mimetype=mimetype,
            )
        )
        return len(data)

    # Buffer type not available python < 3.12, hence type ignore
    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override]
        for line in sequence:
            self.write(line)


class ThreadSafeStderr(Stderr):
    encoding = sys.stderr.encoding
    errors = sys.stderr.errors
    _fileno: int | None = None

    def __init__(
        self, stream: ThreadSafeStream, forward_os_streams: bool = True
    ):
        self._stream = stream
        self._original_fd = sys.stderr.fileno()
        # Expose the underlying binary buffer so that code writing to
        # sys.stderr.buffer keeps working.
        self.buffer: io.BufferedIOBase | None = getattr(
            sys.stderr, "buffer", None
        )
        self._forward_os_streams = forward_os_streams

    def fileno(self) -> int:
        if self._fileno is not None:
            return self._fileno
        raise io.UnsupportedOperation("Stream not redirected, no fileno.")

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        _flush_native_buffer(self)
        self._stream.flush_console()

    def _write_with_mimetype(
        self,
        data: str,
        mimetype: ConsoleMimeType,
        *,
        code: str | None = None,
        cell_id: CellId_t | None = None,
    ) -> int:
        cell_id = self._stream.cell_id if cell_id is None else cell_id
        assert cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                f"write() argument must be a str, not {type(data).__name__}"
            )
        max_bytes = std_stream_max_bytes()
        if sys.getsizeof(data) > max_bytes:
            data = (
                "Warning: marimo truncated a very large console output.\n"
                + data[: int(max_bytes)]
                + " ... "
            )

        self._stream.queue_console(
            ConsoleMsg(
                stream=CellChannel.STDERR,
                cell_id=cell_id,
                data=data,
                mimetype=mimetype,
                code=code,
            )
        )
        return len(data)

    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override]
        for line in sequence:
            self.write(line)


class ThreadSafeStdin(Stdin):
    """Implements a subset of stdin."""

    encoding = sys.stdin.encoding
    errors = sys.stdin.errors

    def __init__(self, stream: ThreadSafeStream):
        self._stream = stream

    def fileno(self) -> int:
        raise io.UnsupportedOperation(
            "marimo's stdin is a pseudofile, which has no fileno."
        )

    def writable(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def _readline_with_prompt(
        self, prompt: str = "", password: bool = False
    ) -> str:
        """Read input from the standard in stream, with an optional prompt."""
        with self._stream.input_lock:
            return self._read_input(prompt, password)

    def _read_input(self, prompt: str, password: bool) -> str:
        require_active_execution()
        assert self._stream.cell_id is not None
        if not isinstance(prompt, str):
            raise TypeError(
                f"prompt must be a str, not {type(prompt).__name__}"
            )

        max_bytes = std_stream_max_bytes()
        if sys.getsizeof(prompt) > max_bytes:
            prompt = (
                "Warning: marimo truncated a very large console output.\n"
                + prompt[: int(max_bytes)]
                + " ... "
            )

        input_id = str(uuid4())
        mimetype: ConsoleMimeType = (
            "text/password" if password else "text/plain"
        )
        self._stream.queue_console(
            ConsoleMsg(
                stream=CellChannel.STDIN,
                cell_id=self._stream.cell_id,
                data=prompt,
                mimetype=mimetype,
                input_id=input_id,
            )
        )

        while True:
            require_active_execution()
            try:
                reply = self._stream.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if reply.input_id == input_id:
                return reply.value


@contextlib.contextmanager
def redirect(standard_stream: Stdout | Stderr) -> Iterator[None]:
    """Forward native writes using the execution or command that opened the pipe."""
    if (
        not isinstance(standard_stream, (ThreadSafeStdout, ThreadSafeStderr))
        or not standard_stream._forward_os_streams
    ):
        yield
        return

    cell_id = standard_stream._stream.cell_id
    assert cell_id is not None
    fd = standard_stream._original_fd
    inheritable = os.get_inheritable(fd)
    outer_fileno = standard_stream._fileno
    with contextlib.ExitStack() as restore:
        _flush_native_buffer(standard_stream)
        saved_fd = os.dup(fd)
        restore.callback(os.close, saved_fd)
        read_fd, write_fd = os.pipe()
        try:
            owner = Context()
            owner.run(RUN_ID_CTX.set, RUN_ID_CTX.get(None))
            if execution := EXECUTION_CTX.get():
                owner.run(EXECUTION_CTX.set, replace(execution, attempt=None))
            reader = threading.Thread(
                target=owner.run,
                args=(
                    _forward_os_stream,
                    standard_stream,
                    read_fd,
                    cell_id,
                ),
                daemon=True,
            )
            Context().run(reader.start)
        except BaseException:
            os.close(read_fd)
            os.close(write_fd)
            raise

        # A child may keep its pipe open beyond this command. Its reader
        # retains the original cell and can finish after we restore the fd.
        restore.callback(reader.join, timeout=0.01)
        try:
            restore.callback(os.dup2, saved_fd, fd, inheritable)
            os.dup2(write_fd, fd, inheritable)
        finally:
            os.close(write_fd)
        restore.callback(_flush_native_buffer, standard_stream)
        standard_stream._fileno = fd
        try:
            yield
        finally:
            standard_stream._fileno = outer_fileno
