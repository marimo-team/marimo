import signal
import sys
import threading
from queue import Queue
from typing import Any
from unittest.mock import Mock

import pytest

from marimo._messaging.notification import InterruptedNotification
from marimo._messaging.serde import serialize_kernel_message
from marimo._messaging.streams import ThreadSafeStream
from marimo._messaging.types import KernelMessage
from marimo._runtime.handlers import construct_interrupt_handler
from marimo._runtime.runtime import Kernel
from marimo._utils.signals import SigintHandler
from tests.conftest import ExecReqProvider, MockedKernel


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
        pipe=pipe, input_queue=Queue[str](), redirect_console=False
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
        pipe=pipe, input_queue=Queue[str](), redirect_console=False
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
