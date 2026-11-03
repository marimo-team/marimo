# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import codecs
import contextlib
import copy
import io
import os
import selectors
import sys
import threading
from array import array
from collections import deque
from contextvars import copy_context
from typing import (
    TYPE_CHECKING,
    Protocol,
)

from marimo import _loggers
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.console_output_worker import (
    ConsoleMsg,
    FlushMarker,
    buffered_writer,
)
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
        return get_context().marimo_config["runtime"]["output_max_bytes"]
    except ContextNotInitializedError:
        return 5_000_000  # 5MB


def std_stream_max_bytes() -> int:
    from marimo._runtime.context import ContextNotInitializedError, get_context

    try:
        return get_context().marimo_config["runtime"]["std_stream_max_bytes"]
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
        input_queue: QueueType[str],
        redirect_console: bool,
        cell_id: CellId_t | None = None,
    ):
        self.pipe = pipe
        self.cell_id = cell_id
        self.redirect_console = redirect_console
        # A single stream is shared by the kernel and the code completion
        # worker. The lock should almost always be uncontended.
        self.stream_lock = threading.Lock()

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
        # The parent stream and thread copy write to the same pipe. Share the
        # transport lock so pipe.send() remains serialized across both views.
        stream.stream_lock = self.stream_lock
        return stream

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
        if self.redirect_console:
            with self.console_msg_cv:
                self.console_msg_queue.append(None)
                self.console_msg_cv.notify()


def _pipe_bytes_available(fd: int) -> int:
    if sys.platform == "win32":
        import _winapi
        import msvcrt

        return _winapi.PeekNamedPipe(msvcrt.get_osfhandle(fd), 0)[0]

    import fcntl
    import termios

    available = array("i", [0])
    fcntl.ioctl(fd, termios.FIONREAD, available, True)
    return available[0]


class _NoOpWatcher:
    """A dummy watcher that does nothing, used when fd redirection is off."""

    def start(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass


_NOOP_WATCHER = _NoOpWatcher()


class Watcher:
    """Watches and redirects a standard stream."""

    def __init__(
        self, standard_stream: ThreadSafeStdout | ThreadSafeStderr
    ) -> None:
        self.standard_stream = standard_stream
        self.fd = self.standard_stream._original_fd
        self.read_fd, self.write_fd = os.pipe()
        self._should_exit = threading.Event()
        self._read_lock = threading.Lock()
        self._error: Exception | None = None
        self._output: ThreadSafeStdout | ThreadSafeStderr | None = None
        self._context = copy_context()
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._wake_read_fd, self._wake_write_fd = os.pipe()
        self.thread = threading.Thread(target=self._forward, daemon=True)
        self.thread.start()

    def _check_error(self) -> None:
        if self._error is not None:
            raise RuntimeError("OS stream reader failed") from self._error

    def _read(self, remaining: int) -> None:
        # The reader and pause hold the same lock through queue insertion.
        # Read only a fixed quota so a background writer cannot extend a drain.
        try:
            while remaining:
                data = os.read(self.read_fd, min(remaining, 1024))
                if not data:
                    raise EOFError("OS stream pipe closed during drain")
                remaining -= len(data)
                text = self._decoder.decode(data)
                if text and self._output is not None:
                    self._context.run(self._output.write, text)
        except Exception as exc:
            self._error = exc
            raise

    def _forward(self) -> None:
        selector: selectors.BaseSelector | None = None
        try:
            if sys.platform != "win32":
                selector = selectors.DefaultSelector()
            if selector is not None:
                selector.register(self.read_fd, selectors.EVENT_READ)
                selector.register(self._wake_read_fd, selectors.EVENT_READ)
            while not self._should_exit.is_set():
                if selector is None:
                    # Windows anonymous pipes cannot be passed to select.
                    # This wait only schedules reads; pause drains synchronously.
                    if self._should_exit.wait(0.01):
                        break
                else:
                    selector.select()
                with self._read_lock:
                    if self._should_exit.is_set():
                        break
                    self._read(_pipe_bytes_available(self.read_fd))
        except Exception as exc:
            with self._read_lock:
                self._error = exc
        finally:
            if selector is not None:
                selector.close()
            os.close(self.read_fd)
            os.close(self._wake_read_fd)

    def start(self) -> None:
        with SigintHandler.defer(), self._read_lock:
            self._check_error()
            self._output = self.standard_stream
            self._context = copy_context()
            fd_dup = os.dup(self.fd)
            try:
                os.dup2(self.write_fd, self.fd)
            except BaseException:
                os.close(fd_dup)
                raise
            self.fd_dup = fd_dup
            self.standard_stream._set_fileno(fd_dup)

    def pause(self) -> None:
        with SigintHandler.defer():
            os.dup2(self.fd_dup, self.fd)
            os.close(self.fd_dup)
            self.standard_stream._set_fileno(None)
            with self._read_lock:
                self._check_error()
                self._read(_pipe_bytes_available(self.read_fd))
                tail = self._decoder.decode(b"", final=True)
                if tail and self._output is not None:
                    self._context.run(self._output.write, tail)
                self._decoder.reset()
                # Inherited writers can still emit between executions.
                output = copy.copy(self.standard_stream)
                output._stream = copy.copy(self.standard_stream._stream)
                output._stream.redirect_console = False
                self._output = output

    def stop(self) -> None:
        self._should_exit.set()
        if sys.platform != "win32":
            with contextlib.suppress(BrokenPipeError):
                os.write(self._wake_write_fd, b"\0")
        os.close(self.write_fd)
        os.close(self._wake_write_fd)
        self.thread.join(timeout=_FLUSH_CONSOLE_TIMEOUT_S)
        if self.thread.is_alive():
            LOGGER.warning("OS stream reader did not stop")


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
        self._watcher: Watcher | _NoOpWatcher = (
            Watcher(self) if forward_os_streams else _NOOP_WATCHER
        )

    def _stop(self) -> None:
        self._watcher.stop()

    def fileno(self) -> int:
        if self._fileno is not None:
            return self._fileno
        raise io.UnsupportedOperation("Stream not redirected, no fileno.")

    def _set_fileno(self, fileno: int | None) -> None:
        self._fileno = fileno

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        self._stream.flush_console()

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        assert self._stream.cell_id is not None
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
        with self._stream.console_msg_cv:
            self._stream.console_msg_queue.append(
                ConsoleMsg(
                    stream=CellChannel.STDOUT,
                    cell_id=self._stream.cell_id,
                    data=data,
                    mimetype=mimetype,
                )
            )
            self._stream.console_msg_cv.notify()
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
        self._watcher: Watcher | _NoOpWatcher = (
            Watcher(self) if forward_os_streams else _NOOP_WATCHER
        )

    def _stop(self) -> None:
        self._watcher.stop()

    def fileno(self) -> int:
        if self._fileno is not None:
            return self._fileno
        raise io.UnsupportedOperation("Stream not redirected, no fileno.")

    def _set_fileno(self, fileno: int | None) -> None:
        self._fileno = fileno

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        self._stream.flush_console()

    def _write_with_mimetype(
        self,
        data: str,
        mimetype: ConsoleMimeType,
        *,
        code: str | None = None,
    ) -> int:
        assert self._stream.cell_id is not None
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

        with self._stream.console_msg_cv:
            self._stream.console_msg_queue.append(
                ConsoleMsg(
                    stream=CellChannel.STDERR,
                    cell_id=self._stream.cell_id,
                    data=data,
                    mimetype=mimetype,
                    code=code,
                )
            )
            self._stream.console_msg_cv.notify()
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

        mimetype: ConsoleMimeType = (
            "text/password" if password else "text/plain"
        )
        with self._stream.console_msg_cv:
            # This sends a prompt request to the frontend.
            self._stream.console_msg_queue.append(
                ConsoleMsg(
                    stream=CellChannel.STDIN,
                    cell_id=self._stream.cell_id,
                    data=prompt,
                    mimetype=mimetype,
                )
            )
            self._stream.console_msg_cv.notify()

        return self._stream.input_queue.get()


@contextlib.contextmanager
def redirect(standard_stream: Stdout | Stderr) -> Iterator[None]:
    """Redirect a standard stream to the frontend."""
    watcher = (
        standard_stream._watcher
        if isinstance(standard_stream, (ThreadSafeStdout, ThreadSafeStderr))
        else _NOOP_WATCHER
    )
    watcher.start()
    try:
        yield
    finally:
        watcher.pause()
