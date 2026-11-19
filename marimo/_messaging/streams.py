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
from functools import cache
from typing import (
    TYPE_CHECKING,
    Protocol,
)
from uuid import uuid4

from marimo import _loggers
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.command_output import ConsoleContext
from marimo._messaging.console_output_worker import (
    ConsoleMsg,
    FlushMarker,
    buffered_writer,
)
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
    from collections.abc import Callable, Iterable, Iterator

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

        # An inherited writer can keep its reader alive beyond redirection.
        self._native_pipes: set[_NativePipe] = set()
        self._native_pipes_lock = threading.Lock()
        self._console_owner: ConsoleContext | None = None
        self._parent_console: ThreadSafeStream | None = None
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
        # A thread can write directly between two buffered writes by its parent.
        stream._parent_console = (
            self if self.redirect_console else self._parent_console
        )
        stream.input_lock = self.input_lock
        # The parent stream and thread copy write to the same pipe. Share the
        # transport lock so pipe.send() remains serialized across both views.
        stream.stream_lock = self.stream_lock
        return stream

    @contextlib.contextmanager
    def own_console(self) -> Iterator[None]:
        previous = self._console_owner
        self._console_owner = ConsoleContext()
        try:
            yield
        finally:
            self._console_owner = previous

    def queue_console(
        self, message: ConsoleMsg, *, redirected_write: bool = False
    ) -> None:
        # Ordinary Python threads write to the redirected stdout/stderr but
        # may not inherit the execution or command context.
        owner = self._console_owner
        if (
            redirected_write
            and owner is not None
            and message.destination is None
            and message.run_id is None
            and message.execution_id is None
        ):
            if owner.execution and owner.execution.cell_id == message.cell_id:
                message.execution_id = owner.execution.id
                message.run_id = owner.run_id
            elif owner.command and owner.command[0] == message.cell_id:
                message.destination = owner.command[1]
        with self.console_msg_cv:
            if not self._console_stopped.is_set():
                self.console_msg_queue.append(message)
                self.console_msg_cv.notify()

    def flush_console(self, *, clear_cell_id: CellId_t | None = None) -> None:
        """Force the buffered console writer to flush immediately.

        Blocks until all pending console messages have been sent to the
        frontend, or until a short timeout elapses if the writer thread
        is no longer alive.  This ensures that stderr/stdout output
        produced during cell execution is delivered before the cell is
        marked idle.
        """
        if self._parent_console is not None:
            self._parent_console.flush_console(clear_cell_id=clear_cell_id)
            return
        if (
            not self.redirect_console
            or threading.current_thread() is self.buffered_console_thread
        ):
            return
        # If the buffered writer isn't alive (e.g., shutdown in progress),
        # enqueuing a marker would never be drained. Bail out early.
        if not self.buffered_console_thread.is_alive():
            return
        with self._native_pipes_lock:
            pipes = self._native_pipes.copy()
        for pipe in pipes:
            active = pipe.stream._active_pipe is pipe
            if active:
                _flush_redirected_stream(pipe.stream)
            if active or pipe.cell_id == clear_cell_id:
                pipe.flush(clear_partial=pipe.cell_id == clear_cell_id)
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


def _pending_bytes(fd: int) -> int:
    if sys.platform == "win32":
        import _winapi
        import msvcrt

        return _winapi.PeekNamedPipe(msvcrt.get_osfhandle(fd))[-2]

    import fcntl
    import termios
    from array import array

    count = array("i", [0])
    fcntl.ioctl(fd, termios.FIONREAD, count)
    return count[0]


def _wait_for_pipe(fd: int, stopped: threading.Event) -> Iterator[None]:
    if sys.platform == "win32":
        # Windows selectors only support sockets.
        while not stopped.is_set():
            try:
                if _pending_bytes(fd):
                    yield
                else:
                    stopped.wait(0.01)
            except BrokenPipeError:
                return
        return

    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while not stopped.is_set():
            if selector.select(timeout=0.1):
                yield


def _pipe_at_eof(fd: int) -> bool:
    if sys.platform == "win32":
        try:
            _pending_bytes(fd)
        except BrokenPipeError:
            return True
        return False

    # An empty pipe is readable only after its last writer closes.
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        return bool(selector.select(0)) and _pending_bytes(fd) == 0


class _NativePipe:
    def __init__(
        self,
        stream: ThreadSafeStdout | ThreadSafeStderr,
        read_end: io.FileIO,
        cell_id: CellId_t,
    ) -> None:
        self.stream = stream
        self._read_end = read_end
        self.cell_id = cell_id
        self._cv = threading.Condition()
        self._forwarded = 0
        self._claimed = False
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def start(self) -> None:
        stream = self.stream._stream
        with stream._native_pipes_lock:
            stream._native_pipes.add(self)
        try:
            owner = ConsoleContext().for_native_writer()
            reader = threading.Thread(
                target=self._forward, args=(owner,), daemon=True
            )
            Context().run(reader.start)
        except BaseException:
            # Thread.start() can be interrupted after the thread is running.
            with self._cv:
                if not self._claimed:
                    self._close()
            raise

    def _close(self) -> None:
        self._read_end.close()
        stream = self.stream._stream
        with stream._native_pipes_lock:
            stream._native_pipes.discard(self)

    def _drain_locked(self) -> None:
        if self._read_end.closed:
            return
        # A child may keep writing indefinitely. Only wait for the bytes
        # already in the pipe when the caller requested the flush.
        try:
            pending = _pending_bytes(self._read_end.fileno())
        except BrokenPipeError:
            return
        target = self._forwarded + pending
        if pending and not self._cv.wait_for(
            lambda: self._read_end.closed or self._forwarded >= target,
            timeout=_FLUSH_CONSOLE_TIMEOUT_S,
        ):
            LOGGER.warning("Timed out waiting for native console output")

    def flush(self, *, clear_partial: bool = False) -> None:
        with self._cv:
            self._drain_locked()
            if clear_partial:
                self._decoder.reset()

    def finish(self) -> None:
        with self._cv:
            self._drain_locked()
            if self._read_end.closed or not _pipe_at_eof(
                self._read_end.fileno()
            ):
                return
            # The reader also publishes any incomplete character at EOF.
            if not self._cv.wait_for(
                lambda: self._read_end.closed, timeout=_FLUSH_CONSOLE_TIMEOUT_S
            ):
                LOGGER.warning("Timed out waiting for native console EOF")

    def _forward(self, owner: ConsoleContext) -> None:
        with self._cv:
            if self._read_end.closed:
                return
            self._claimed = True
        fd = self._read_end.fileno()
        try:
            with owner.install():
                for _ in _wait_for_pipe(
                    fd, self.stream._stream._console_stopped
                ):
                    with self._cv:
                        data = os.read(fd, 4096)
                        if not data:
                            break
                        if text := self._decoder.decode(data):
                            self.stream._write_with_mimetype(
                                text, "text/plain", cell_id=self.cell_id
                            )
                        self._forwarded += len(data)
                        self._cv.notify_all()
                with self._cv:
                    if tail := self._decoder.decode(b"", final=True):
                        self.stream._write_with_mimetype(
                            tail, "text/plain", cell_id=self.cell_id
                        )
        finally:
            with self._cv:
                self._close()
                self._cv.notify_all()


@cache
def _c_stdio_flush(fd: int) -> Callable[[], int] | None:
    # C extensions write through libc's FILE*, separately buffered from Python.
    if fd not in (1, 2):
        return None
    from functools import partial

    try:
        import ctypes

        if sys.platform == "win32":
            libc = ctypes.CDLL("ucrtbase")
            get_stream = libc.__acrt_iob_func
            get_stream.argtypes = [ctypes.c_uint]
            get_stream.restype = ctypes.c_void_p
            c_stream = get_stream(fd)
        else:
            libc = ctypes.CDLL(None)
            name = "stdout" if fd == 1 else "stderr"
            if sys.platform == "darwin":
                name = f"__{name}p"
            c_stream = ctypes.c_void_p.in_dll(libc, name).value
        if c_stream is not None:
            flush = libc.fflush
            flush.argtypes = [ctypes.c_void_p]
            return partial(flush, c_stream)
    except (ImportError, AttributeError, OSError, ValueError):
        # Some embedded interpreters don't expose the platform's C stdio.
        pass
    return None


def _flush_redirected_stream(
    stream: ThreadSafeStdout | ThreadSafeStderr,
) -> None:
    if not stream._original_stream.closed:
        stream._original_stream.flush()
    if flush := _c_stdio_flush(stream._original_fd):
        flush()


def _flush_native_buffer(stream: ThreadSafeStdout | ThreadSafeStderr) -> None:
    if stream.buffer is not None and not stream.buffer.closed:
        stream.buffer.flush()


# NB: Python doesn't provide a standard out class to inherit from, so
# we inherit from TextIOBase.
class ThreadSafeStdout(Stdout):
    encoding = sys.stdout.encoding
    errors = sys.stdout.errors
    _active_pipe: _NativePipe | None = None

    def __init__(
        self, stream: ThreadSafeStream, forward_os_streams: bool = True
    ):
        self._stream = stream
        self._original_stream = sys.stdout
        self._original_fd = self._original_stream.fileno()
        # Expose the underlying binary buffer so that code writing to
        # sys.stdout.buffer (e.g. package installation logging) keeps working.
        self.buffer: io.BufferedIOBase | None = getattr(
            sys.stdout, "buffer", None
        )
        self._forward_os_streams = forward_os_streams

    def fileno(self) -> int:
        if self._active_pipe is not None:
            return self._original_fd
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
        redirected_write = cell_id is None
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
            ),
            redirected_write=redirected_write,
        )
        return len(data)

    # Buffer type not available python < 3.12, hence type ignore
    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override]
        for line in sequence:
            self.write(line)


class ThreadSafeStderr(Stderr):
    encoding = sys.stderr.encoding
    errors = sys.stderr.errors
    _active_pipe: _NativePipe | None = None

    def __init__(
        self, stream: ThreadSafeStream, forward_os_streams: bool = True
    ):
        self._stream = stream
        self._original_stream = sys.stderr
        self._original_fd = self._original_stream.fileno()
        # Expose the underlying binary buffer so that code writing to
        # sys.stderr.buffer keeps working.
        self.buffer: io.BufferedIOBase | None = getattr(
            sys.stderr, "buffer", None
        )
        self._forward_os_streams = forward_os_streams

    def fileno(self) -> int:
        if self._active_pipe is not None:
            return self._original_fd
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
        redirected_write = cell_id is None
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
            ),
            redirected_write=redirected_write,
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
        require_active_execution()
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

        return _wait_for_reply(self._stream, input_id, execution=True)


def _wait_for_reply(
    stream: ThreadSafeStream, input_id: str, *, execution: bool
) -> str:
    while True:
        if execution:
            require_active_execution()
        try:
            reply = stream.input_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        if reply.input_id == input_id:
            return reply.value


class PdbInput(io.StringIO):
    """Pdb's command reader while inspecting a saved traceback."""

    def __init__(self, stream: ThreadSafeStream, cell_id: CellId_t) -> None:
        super().__init__()
        self._stream = stream
        self._cell_id = cell_id

    def readline(self, size: int | None = -1, /) -> str:  # type: ignore[override]
        from marimo._messaging.notification import PdbInputNotification
        from marimo._messaging.notification_utils import broadcast_notification

        del size
        with self._stream.input_lock:
            input_id = str(uuid4())
            self._stream.flush_console()
            try:
                broadcast_notification(
                    PdbInputNotification(self._cell_id, input_id=input_id),
                    self._stream,
                )
                return (
                    _wait_for_reply(self._stream, input_id, execution=False)
                    + "\n"
                )
            finally:
                broadcast_notification(
                    PdbInputNotification(self._cell_id, input_id=None),
                    self._stream,
                )


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
    outer_pipe = standard_stream._active_pipe
    with contextlib.ExitStack() as restore:
        _flush_redirected_stream(standard_stream)
        with SigintHandler.defer():
            saved_fd = os.dup(fd)
            restore.callback(os.close, saved_fd)
            read_fd, write_fd = os.pipe()
            with io.FileIO(write_fd, "wb") as writer:
                pipe = _NativePipe(
                    standard_stream, io.FileIO(read_fd, "rb"), cell_id
                )
                pipe.start()
                restore.callback(pipe.finish)
                restore.callback(os.dup2, saved_fd, fd, inheritable)
                os.dup2(writer.fileno(), fd, inheritable)
            restore.callback(_flush_redirected_stream, standard_stream)

        try:
            standard_stream._active_pipe = pipe
            yield
        finally:
            standard_stream._active_pipe = outer_pipe
