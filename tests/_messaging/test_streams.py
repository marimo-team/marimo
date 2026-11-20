from __future__ import annotations

import errno
import gc
import os
import signal
import subprocess
import sys
import tempfile
import threading
import weakref
from contextvars import Context, ContextVar
from queue import Queue
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

from marimo._messaging import streams as messaging_streams
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.command_output import command_console
from marimo._messaging.context import execution_id_context
from marimo._messaging.input import InputReply
from marimo._messaging.notification import (
    CallbackOutputNotification,
    CellNotification,
    InterruptedNotification,
    PdbOutputNotification,
)
from marimo._messaging.notification_utils import CellNotificationUtils
from marimo._messaging.serde import (
    deserialize_kernel_message,
    serialize_kernel_message,
)
from marimo._messaging.streams import (
    QueuePipe,
    ThreadSafeStderr,
    ThreadSafeStdout,
    ThreadSafeStream,
    redirect,
)
from marimo._messaging.types import KernelMessage, KernelStreams
from marimo._runtime.context import get_context
from marimo._runtime.handlers import construct_interrupt_handler
from marimo._runtime.output import _output
from marimo._runtime.redirect_streams import redirect_streams
from marimo._runtime.runtime import Kernel
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._session.state.session_view import SessionView
from marimo._utils.signals import SigintHandler
from tests._runtime._helpers.streams import MockStream
from tests.conftest import ExecReqProvider, MockedKernel

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def test_debugger_does_not_capture_other_streams_or_executions() -> None:
    messages = Queue[KernelMessage]()
    debugger, other = [
        ThreadSafeStream(QueuePipe(messages), Queue(), True, cell_id="cell")
        for _ in range(2)
    ]
    first, second = [
        ThreadSafeStdout(stream, forward_os_streams=False)
        for stream in (debugger, other)
    ]
    try:
        with (
            command_console("cell", PdbOutputNotification),
            debugger.own_console(),
        ):
            with execution_id_context("cell", "earlier"):
                first.write("background")
            Context().run(second.write, "other session")
        first.write("after debugger")
        debugger.flush_console()
        other.flush_console()
        writes = {}
        for _ in range(3):
            msg = deserialize_kernel_message(messages.get(timeout=2))
            assert isinstance(msg, CellNotification)
            assert isinstance(msg.console, CellOutput)
            writes[msg.console.data] = msg.execution_id
        assert writes == {
            "background": "earlier",
            "other session": None,
            "after debugger": None,
        }
    finally:
        debugger.stop()
        other.stop()


def test_inherited_fd_keeps_its_execution_during_a_later_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), redirect_console=True
    )
    try:
        with open(os.devnull, "w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            stdout = ThreadSafeStdout(stream)
            stream.cell_id = "first"
            with (
                execution_id_context("first", "old-execution"),
                redirect(stdout),
            ):
                os.write(stdout.fileno(), b"\xe2")
                stdout.flush()
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=stdout,
                )
            with child:
                stream.cell_id = "second"
                with (
                    command_console("second", CallbackOutputNotification),
                    redirect(stdout),
                ):
                    child.communicate(b"\x82\xac from subprocess", timeout=5)
                    assert child.returncode == 0
                    os.write(stdout.fileno(), b"from callback")
            output = [
                deserialize_kernel_message(messages.get(timeout=2))
                for _ in range(2)
            ]
            (execution,) = (
                entry
                for entry in output
                if isinstance(entry, CellNotification)
            )
            (callback,) = (
                entry
                for entry in output
                if isinstance(entry, CallbackOutputNotification)
            )
            assert (execution.cell_id, execution.execution_id) == (
                "first",
                "old-execution",
            )
            assert execution.console is not None
            assert not isinstance(execution.console, list)
            assert execution.console.data == "€ from subprocess"
            assert callback.cell_id == "second"
            assert [entry.data for entry in callback.entries] == [
                "from callback"
            ]
    finally:
        stream.stop()


def test_callback_media_interleaves_with_buffered_stdout() -> None:
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), True, cell_id="cell"
    )
    out = ThreadSafeStdout(stream, forward_os_streams=False)
    try:
        with command_console("cell", CallbackOutputNotification):
            out.write("before")
            CellNotificationUtils.broadcast_console_output(
                channel=CellChannel.MEDIA,
                mimetype="text/html",
                data="<b>media</b>",
                cell_id="cell",
                status=None,
                stream=stream,
            )
            out.write("after")
            stream.flush_console()

        view = SessionView()
        live = []
        for _ in range(3):
            msg = deserialize_kernel_message(messages.get(timeout=2))
            assert isinstance(msg, CallbackOutputNotification)
            live.extend((entry.channel, entry.data) for entry in msg.entries)
            view.add_notification(msg)
        exported = [
            (entry.channel, entry.data)
            for entry in view.cell_console("cell", include_callbacks=True)
        ]
        assert (
            live
            == exported
            == [
                ("stdout", "before"),
                ("media", "<b>media</b>"),
                ("stdout", "after"),
            ]
        )
    finally:
        stream.stop()


@pytest.mark.parametrize(
    ("name", "wrapper"),
    [("stdout", ThreadSafeStdout), ("stderr", ThreadSafeStderr)],
)
def test_buffered_native_writes_stay_with_their_owner(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    wrapper: type[ThreadSafeStdout | ThreadSafeStderr],
) -> None:
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), True, cell_id="public"
    )
    try:
        with open(os.devnull, "w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, name, terminal)
            out = wrapper(stream)
            assert out.buffer is not None
            with execution_id_context("public", "evaluation"), redirect(out):
                out.buffer.write(b"public")
                stream.cell_id = "private"
                with (
                    command_console("private", PdbOutputNotification),
                    redirect(out),
                ):
                    out.buffer.write(b"private")
                    terminal.write(" text")
                terminal.flush()
        writes = {}
        for _ in range(2):
            msg = deserialize_kernel_message(messages.get(timeout=2))
            if isinstance(msg, PdbOutputNotification):
                (entry,) = msg.entries
                writes[msg.cell_id] = (msg.name, entry.data)
            else:
                assert isinstance(msg, CellNotification)
                assert isinstance(msg.console, CellOutput)
                writes[msg.cell_id] = (msg.execution_id, msg.console.data)
        assert writes == {
            "public": ("evaluation", "public"),
            "private": ("pdb-output", "private text"),
        }
    finally:
        stream.stop()


def test_c_stdio_buffer_is_flushed_before_leaving_cell(
    capfd: pytest.CaptureFixture[str],
) -> None:
    import ctypes

    libc = ctypes.CDLL("ucrtbase" if sys.platform == "win32" else None)
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), True, cell_id="first"
    )
    try:
        with capfd.disabled():
            stdout = ThreadSafeStdout(stream)
            with execution_id_context("first", "execution"), redirect(stdout):
                assert libc.putchar(ord("x")) == ord("x")

            stream.cell_id = "second"
            with redirect(stdout):
                libc.fflush(None)
        msg = deserialize_kernel_message(messages.get(timeout=2))
        assert isinstance(msg, CellNotification)
        assert isinstance(msg.console, CellOutput)
        assert (msg.cell_id, msg.execution_id, msg.console.data) == (
            "first",
            "execution",
            "x",
        )
    finally:
        stream.stop()


@pytest.mark.parametrize(
    ("before_clear", "before_idle", "expected"),
    [
        (
            b"before clear",
            b"before idle",
            ["before clear", "clear", "before idle", "idle"],
        ),
        (b"\xe9", b"", ["clear", "idle"]),
        (b"", b"\xe9", ["clear", "�", "idle"]),
    ],
)
async def test_buffered_native_output_precedes_clear_and_idle(
    k: Kernel,
    exec_req: ExecReqProvider,
    monkeypatch: pytest.MonkeyPatch,
    before_clear: bytes,
    before_idle: bytes,
    expected: list[str],
) -> None:
    stream = MockStream(redirect_console=True)
    try:
        with (
            tempfile.TemporaryFile("w") as terminal,
            monkeypatch.context() as patch,
        ):
            patch.setattr(sys, "stdout", terminal)
            streams = KernelStreams(
                stream=stream,
                stdout=ThreadSafeStdout(stream),
                stderr=ThreadSafeStderr(stream),
                stdin=None,
            )
            patch.setattr(k, "_streams", streams)
            patch.setattr(get_context(), "stream", stream)
            request = exec_req.get(
                f"""
                import sys
                import marimo as mo

                sys.stdout.buffer.write({before_clear!r})
                mo.output.clear_console()
                sys.stdout.buffer.write({before_idle!r})
                """
            )
            await k.run([request])
            stream.flush_console()
        events = []
        for msg in stream.cell_notifications:
            if isinstance(msg.console, CellOutput):
                events.append(msg.console.data)
            elif msg.console == [] and msg.status is None:
                events.append("clear")
            elif msg.status == "idle":
                events.append("idle")
        assert events == expected
    finally:
        stream.stop()


def test_thread_clear_drains_inherited_writer_and_resets_its_decoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), True, cell_id="cell"
    )
    try:
        with open(os.devnull, "w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            stdout = ThreadSafeStdout(stream)
            before = set(threading.enumerate())
            with execution_id_context("cell", "execution"), redirect(stdout):
                writer = os.dup(stdout.fileno())
                thread_stream = stream.copy_for_thread()
                (reader,) = set(threading.enumerate()) - before
            try:
                os.write(writer, b"before\xe2")
                ctx = SimpleNamespace(
                    stream=thread_stream, execution_context=True
                )
                patch.setattr(_output, "get_context", lambda: ctx)
                with execution_id_context("cell", "execution"):
                    _output.clear_console()
                os.write(writer, b"\x82\xacafter")
            finally:
                os.close(writer)
                reader.join(timeout=2)
            assert not reader.is_alive()
            assert not stream._native_pipes

        events = []
        for _ in range(3):
            msg = deserialize_kernel_message(messages.get(timeout=2))
            assert isinstance(msg, CellNotification)
            events.append(
                (
                    msg.cell_id,
                    msg.execution_id,
                    msg.console.data
                    if isinstance(msg.console, CellOutput)
                    else msg.console,
                )
            )
        assert events == [
            ("cell", "execution", "before"),
            ("cell", "execution", []),
            ("cell", "execution", "��after"),
        ]
    finally:
        stream.stop()


def test_clearing_another_cell_preserves_pending_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), True, cell_id="writing"
    )
    try:
        with open(os.devnull, "w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            stdout = ThreadSafeStdout(stream)
            with redirect(stdout):
                os.write(stdout.fileno(), b"\xe2")
                stream.flush_console(clear_cell_id="clearing")
                os.write(stdout.fileno(), b"\x82\xac")
        stream.flush_console()
        msg = deserialize_kernel_message(messages.get(timeout=2))
        assert isinstance(msg, CellNotification)
        assert isinstance(msg.console, CellOutput)
        assert (msg.cell_id, msg.console.data) == ("writing", "€")
    finally:
        stream.stop()


def test_interrupt_during_reader_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    handler = SigintHandler(interrupt)
    start = threading.Thread.start
    started = []

    def start_then_interrupt(reader: threading.Thread) -> None:
        start(reader)
        handler(signal.SIGINT, None)
        started.append(reader)

    stream = ThreadSafeStream(
        QueuePipe(Queue()), Queue(), True, cell_id="cell"
    )
    try:
        path = tmp_path / "stdout"
        with path.open("w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            out = ThreadSafeStdout(stream)
            patch.setattr(threading.Thread, "start", start_then_interrupt)
            with pytest.raises(KeyboardInterrupt), redirect(out):
                pytest.fail(
                    "Pending interrupt should run before the cell starts"
                )
            os.write(terminal.fileno(), b"restored")

        (reader,) = started
        reader.join(timeout=2)
        assert not reader.is_alive()
        assert path.read_bytes() == b"restored"
    finally:
        stream.stop()


def test_plain_sigint_after_reader_claims_fd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready = threading.Event()
    resume = threading.Event()
    fds: list[int] = []
    readers: list[threading.Thread] = []
    errors: list[threading.ExceptHookArgs] = []
    wait_for_pipe = messaging_streams._wait_for_pipe
    start = threading.Thread.start

    def wait_for_interrupt(
        fd: int, stopped: threading.Event
    ) -> Iterator[None]:
        fds.append(fd)
        ready.set()
        assert resume.wait(timeout=5)
        yield from wait_for_pipe(fd, stopped)

    def interrupt_start(reader: threading.Thread) -> None:
        readers.append(reader)
        start(reader)
        assert ready.wait(timeout=5)
        signal.raise_signal(signal.SIGINT)

    stream = ThreadSafeStream(
        QueuePipe(Queue()), Queue(), True, cell_id="cell"
    )
    handler = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        with open(os.devnull, "w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            out = ThreadSafeStdout(stream)
            patch.setattr(
                messaging_streams, "_wait_for_pipe", wait_for_interrupt
            )
            patch.setattr(threading.Thread, "start", interrupt_start)
            patch.setattr(threading, "excepthook", errors.append)
            with pytest.raises(KeyboardInterrupt), redirect(out):
                pytest.fail("Interrupted startup entered the cell")
            (fd,) = fds
            (reader,) = readers
            try:
                os.fstat(fd)  # The live reader still owns it.
            finally:
                resume.set()
                reader.join(timeout=5)
            assert not reader.is_alive()
            assert errors == []
            with pytest.raises(OSError) as exc:
                os.fstat(fd)
            assert exc.value.errno == errno.EBADF
    finally:
        resume.set()
        signal.signal(signal.SIGINT, handler)
        stream.stop()


def test_idle_inherited_fd_releases_the_callers_context_and_retires_on_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Payload:
        pass

    stream = ThreadSafeStream(
        QueuePipe(Queue()), Queue(), True, cell_id="cell"
    )
    state = ContextVar[Payload]("notebook-state")
    try:
        with open(os.devnull, "w") as terminal, monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            out = ThreadSafeStdout(stream)
            value = Payload()
            retained = weakref.ref(value)
            token = state.set(value)
            before = set(threading.enumerate())
            with redirect(out):
                writer = os.dup(out.fileno())
                (reader,) = set(threading.enumerate()) - before
            try:
                state.reset(token)
                del value
                gc.collect()
                assert retained() is None

                stream.stop()
                reader.join(timeout=2)
                assert not reader.is_alive()
            finally:
                os.close(writer)
    finally:
        stream.stop()


def test_native_writes_from_a_cell_run_inside_scratch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = Queue[KernelMessage]()
    stream = ThreadSafeStream(
        QueuePipe(messages), Queue(), redirect_console=True
    )
    try:
        with (
            open(os.devnull, "w") as terminal,
            open(os.devnull, "w") as errors,
        ):
            monkeypatch.setattr(sys, "stdout", terminal)
            monkeypatch.setattr(sys, "stderr", errors)
            stdout, stderr = ThreadSafeStdout(stream), ThreadSafeStderr(stream)
            with (
                execution_id_context(SCRATCH_CELL_ID, "outer"),
                redirect_streams(
                    SCRATCH_CELL_ID, stream, stdout, stderr, None
                ),
            ):
                with (
                    execution_id_context("cell", "inner"),
                    redirect_streams("cell", stream, stdout, stderr, None),
                ):
                    os.write(sys.stderr.fileno(), b"inner")
                os.write(sys.stdout.fileno(), b"outer")

        writes = {}
        for _ in range(2):
            msg = deserialize_kernel_message(messages.get(timeout=2))
            assert isinstance(msg, CellNotification)
            assert msg.console is not None
            assert not isinstance(msg.console, list)
            writes[msg.cell_id] = (
                msg.execution_id,
                msg.console.channel,
                msg.console.data,
            )
        assert writes == {
            "cell": ("inner", "stderr", "inner"),
            SCRATCH_CELL_ID: ("outer", "stdout", "outer"),
        }
    finally:
        stream.stop()


@pytest.mark.parametrize("custom_handler", [False, True])
@pytest.mark.parametrize("broken_pipe", [False, True])
def test_stream_write_preserves_signal_configuration(
    monkeypatch: pytest.MonkeyPatch,
    custom_handler: bool,
    broken_pipe: bool,
) -> None:
    handler = Mock() if custom_handler else construct_interrupt_handler()

    # Installing even the same handler resets POSIX syscall-restart behavior.
    def forbid_signal_change(*_args: Any) -> None:
        pytest.fail("Stream writes must not change OS signal configuration")

    pipe = Mock()
    if broken_pipe:
        pipe.send.side_effect = BrokenPipeError
    stream = ThreadSafeStream(
        pipe=pipe, input_queue=Queue[InputReply](), redirect_console=False
    )
    message = serialize_kernel_message(InterruptedNotification())
    with monkeypatch.context() as patch:
        patch.setattr(signal, "getsignal", lambda _signum: handler)
        patch.setattr(signal, "signal", forbid_signal_change)
        if hasattr(signal, "siginterrupt"):
            patch.setattr(signal, "siginterrupt", forbid_signal_change)
        stream.write(message)
    pipe.send.assert_called_once_with(message)


def test_stream_write_defers_forwarded_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_states: list[bool] = []
    pipe = Mock()
    stream = ThreadSafeStream(
        pipe=pipe, input_queue=Queue[InputReply](), redirect_console=False
    )
    handler = SigintHandler(
        lambda *_args: lock_states.append(stream.stream_lock.locked())
    )

    def forward_interrupt(signum: int, frame: Any) -> None:
        handler(signum, frame)

    # A user-installed handler can forward SIGINT to marimo's saved handler.
    monkeypatch.setattr(signal, "getsignal", lambda _signum: forward_interrupt)
    pipe.send.side_effect = lambda _message: forward_interrupt(
        signal.SIGINT, None
    )
    stream.write(KernelMessage(b"output"))
    assert lock_states == [False]


class _SerializedPipe:
    def __init__(self) -> None:
        self.messages: list[KernelMessage] = []
        self.entered_first_send = threading.Event()
        self.release_first_send = threading.Event()
        self.lock = threading.Lock()
        self.active_sends = 0
        self.overlapped = False

    def send(self, message: KernelMessage) -> None:
        with self.lock:
            self.active_sends += 1
            if self.active_sends > 1:
                self.overlapped = True
            should_block = len(self.messages) == 0
            self.messages.append(message)
            if should_block:
                self.entered_first_send.set()

        if should_block:
            assert self.release_first_send.wait(timeout=1)

        with self.lock:
            self.active_sends -= 1


def test_thread_stream_copy_serializes_writes_to_shared_transport() -> None:
    pipe = _SerializedPipe()
    stream = ThreadSafeStream(
        pipe=pipe,
        input_queue=Queue[Any](),
        redirect_console=True,
    )

    try:
        copied = stream.copy_for_thread()
        assert copied.redirect_console is False

        copied_writer_started = threading.Event()

        def write_copy() -> None:
            copied_writer_started.set()
            copied.write(KernelMessage(b"copy"))

        parent_writer = threading.Thread(
            target=stream.write, args=(KernelMessage(b"parent"),)
        )
        copied_writer = threading.Thread(target=write_copy)

        parent_writer.start()
        assert pipe.entered_first_send.wait(timeout=1)
        copied_writer.start()
        assert copied_writer_started.wait(timeout=1)
        copied_writer.join(timeout=0.1)
        assert copied_writer.is_alive()
        assert pipe.messages == [KernelMessage(b"parent")]
        assert not pipe.overlapped

        pipe.release_first_send.set()
        parent_writer.join(timeout=1)
        copied_writer.join(timeout=1)

        assert not parent_writer.is_alive()
        assert not copied_writer.is_alive()
        assert pipe.messages == [
            KernelMessage(b"parent"),
            KernelMessage(b"copy"),
        ]
        assert not pipe.overlapped
    finally:
        stream.stop()


# Make sure that standard in is installed; stdin is not writable so we
# just check that its methods are callable and return mocked values.
class TestStdin:
    @staticmethod
    async def test_encoding(mocked_kernel: MockedKernel) -> None:
        assert mocked_kernel.stdin.encoding == sys.stdin.encoding

    @staticmethod
    async def test_input_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run([exec_req.get("output = input('hello')")])
        assert k.globals["output"] == "hello"

    @staticmethod
    async def test_readline_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [exec_req.get("import sys; output = sys.stdin.readline()")]
        )
        assert k.globals["output"] == "\n"

    @staticmethod
    async def test_readlines_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [exec_req.get("import sys; output = sys.stdin.readlines()")]
        )
        assert k.globals["output"] == ["\n"]

    @staticmethod
    async def test_builtin_input_with_empty_response(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        # Bypasses the cell-scoped input override, exercising the same
        # readline()-based path that rich/click/getpass/pdb hit. Must not
        # raise EOFError on an empty submission.
        await k.run(
            [exec_req.get("import builtins; output = builtins.input()")]
        )
        assert k.globals["output"] == ""

    @staticmethod
    async def test_getpass_installed(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [exec_req.get("import getpass; output = getpass.getpass('pwd: ')")]
        )
        assert k.globals["output"] == "pwd: "


class TestStdout:
    @staticmethod
    async def test_encoding(mocked_kernel: MockedKernel) -> None:
        assert mocked_kernel.stdout.encoding == sys.stdout.encoding

    @staticmethod
    async def test_fileno(k: Kernel, exec_req: ExecReqProvider) -> None:
        await k.run([exec_req.get("import sys; fileno = sys.stdout.fileno()")])
        assert k.globals["fileno"] is not None

    @staticmethod
    async def test_print(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [exec_req.get("print('hello'); print('there')")]
        )
        assert mocked_kernel.stdout.messages == ["hello", "\n", "there", "\n"]

    @staticmethod
    async def test_write(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [exec_req.get("import sys; sys.stdout.write('hello')")]
        )
        assert mocked_kernel.stdout.messages == ["hello"]

    @staticmethod
    async def test_writelines(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    "import sys; sys.stdout.writelines(['hello', 'there'])"
                )
            ]
        )
        assert mocked_kernel.stdout.messages == ["hello", "there"]


class TestStderr:
    @staticmethod
    async def test_encoding(mocked_kernel: MockedKernel) -> None:
        assert mocked_kernel.stderr.encoding == sys.stderr.encoding

    @staticmethod
    async def test_fileno(k: Kernel, exec_req: ExecReqProvider) -> None:
        await k.run([exec_req.get("import sys; fileno = sys.stderr.fileno()")])
        assert k.globals["fileno"] is not None

    @staticmethod
    async def test_write(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [exec_req.get("import sys; sys.stderr.write('hello')")]
        )
        assert mocked_kernel.stderr.messages == ["hello"]

    @staticmethod
    async def test_writelines(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    "import sys; sys.stderr.writelines(['hello', 'there'])"
                )
            ]
        )
        assert mocked_kernel.stderr.messages == ["hello", "there"]


class TestStrSubclassCoercion:
    """Verify str subclasses (e.g. loguru Message) are coerced to plain str."""

    @staticmethod
    async def test_stdout_str_subclass(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    """
                    import sys

                    class _TaggedStr(str):
                        pass

                    _msg = _TaggedStr("tagged hello")
                    _msg.extra = {"key": "value"}
                    sys.stdout.write(_msg)
                    """
                )
            ]
        )
        assert mocked_kernel.stdout.messages == ["tagged hello"]
        for m in mocked_kernel.stdout.messages:
            assert type(m) is str

    @staticmethod
    async def test_stderr_str_subclass(
        mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        await mocked_kernel.k.run(
            [
                exec_req.get(
                    """
                    import sys

                    class _TaggedStr(str):
                        pass

                    _msg = _TaggedStr("tagged error")
                    _msg.record = {"level": "ERROR"}
                    sys.stderr.write(_msg)
                    """
                )
            ]
        )
        assert mocked_kernel.stderr.messages == ["tagged error"]
        for m in mocked_kernel.stderr.messages:
            assert type(m) is str


async def test_import_multiprocessing(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    # https://github.com/marimo-team/marimo/issues/684
    #
    # On Windows this also guards against the pytest-spawn interaction:
    # __main__.__file__ must not point at the pytest.exe zipapp, or the
    # Manager child's multiprocessing.spawn._fixup_main_from_path will
    # runpy.run_path() pytest itself and the parent hangs on reader.recv().
    # See the _fake_main_file fixture in tests/conftest.py.
    await mocked_kernel.k.run(
        [
            exec_req.get(
                """
                from multiprocessing import Manager
                Manager().dict()
                print("hello")
                """
            )
        ]
    )
    assert mocked_kernel.stdout.messages == ["hello", "\n"]
