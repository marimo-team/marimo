import asyncio
import json
from collections.abc import Generator
from functools import partial
from unittest.mock import Mock

import pytest

from marimo._messaging.cell_output import CellOutput
from marimo._messaging.input import InputReply
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._pyodide.streams import (
    PyodideStderr,
    PyodideStdin,
    PyodideStdout,
    PyodideStream,
)
from marimo._runtime.execution import ExecutionAttempt
from marimo._types.ids import CellId_t

cell_id = CellId_t("test-cell-id")


def test_pyodide_console_io_without_cell_is_usage_error() -> None:
    stream = PyodideStream(Mock(), asyncio.Queue[str]())
    with asyncio.Runner():
        for operation in (
            partial(PyodideStdout(stream).write, "output"),
            partial(PyodideStderr(stream).write, "output"),
            PyodideStdin(stream).readline,
        ):
            with pytest.raises(
                RuntimeError, match="notebook cell"
            ) as exc_info:
                operation()
            assert exc_info.type is RuntimeError


@pytest.fixture
def pyodide_pipe() -> Mock:
    return Mock()


@pytest.fixture
def pyodide_input_queue() -> asyncio.Queue[str | InputReply]:
    return asyncio.Queue()


@pytest.fixture
def pyodide_(
    pyodide_pipe: Mock,
    pyodide_input_queue: asyncio.Queue[str | InputReply],
) -> PyodideStream:
    return PyodideStream(pyodide_pipe, pyodide_input_queue, cell_id)


@pytest.fixture
def pyodide_stdout(pyodide_: PyodideStream) -> PyodideStdout:
    return PyodideStdout(pyodide_)


@pytest.fixture
def pyodide_stderr(pyodide_: PyodideStream) -> PyodideStderr:
    return PyodideStderr(pyodide_)


@pytest.fixture
def pyodide_stdin(
    pyodide_: PyodideStream,
) -> Generator[PyodideStdin, None, None]:
    with asyncio.Runner():
        yield PyodideStdin(pyodide_)


class TestPyodideStream:
    def test_write(self, pyodide_: PyodideStream, pyodide_pipe: Mock) -> None:
        data = {"key": "value"}
        pyodide_.write(data)
        pyodide_pipe.assert_called_once_with(data)

    def test_copy_for_thread(
        self,
        pyodide_: PyodideStream,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str | InputReply],
    ) -> None:
        copied = pyodide_.copy_for_thread()

        assert copied is not pyodide_
        assert copied.pipe is pyodide_pipe
        assert copied.input_queue is pyodide_input_queue
        assert copied.cell_id == pyodide_.cell_id


class TestPyodideStdout:
    def test_writable(self, pyodide_stdout: PyodideStdout) -> None:
        assert pyodide_stdout.writable() is True

    def test_readable(self, pyodide_stdout: PyodideStdout) -> None:
        assert pyodide_stdout.readable() is False

    def test_seekable(self, pyodide_stdout: PyodideStdout) -> None:
        assert pyodide_stdout.seekable() is False

    def test_write(
        self, pyodide_stdout: PyodideStdout, pyodide_pipe: Mock
    ) -> None:
        data = "test output"
        pyodide_stdout.write(data)
        assert pyodide_pipe.call_count == 1
        msg_bytes = pyodide_pipe.call_args[0][0]
        msg = json.loads(msg_bytes)
        assert msg["op"] == "cell-op"
        assert msg["cell_id"] == pyodide_stdout.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == data

    def test_writelines(
        self, pyodide_stdout: PyodideStdout, pyodide_pipe: Mock
    ) -> None:
        lines = ["line1\n", "line2\n", "line3\n"]
        pyodide_stdout.writelines(lines)
        assert pyodide_pipe.call_count == 3


class TestPyodideStderr:
    @pytest.mark.parametrize("code", [None, "raise ValueError('failed')"])
    def test_traceback_source_forwarding(
        self,
        pyodide_stderr: PyodideStderr,
        pyodide_pipe: Mock,
        code: str | None,
    ) -> None:
        pyodide_stderr._write_with_mimetype(
            "ValueError: failed",
            mimetype="application/vnd.marimo+traceback",
            code=code,
        )
        pyodide_pipe.assert_called_once()
        console = json.loads(pyodide_pipe.call_args.args[0])["console"]
        assert console["data"] == "ValueError: failed"
        assert console["mimetype"] == "application/vnd.marimo+traceback"
        if code is None:
            assert "code" not in console
        else:
            assert console["code"] == code

    def test_writable(self, pyodide_stderr: PyodideStderr) -> None:
        assert pyodide_stderr.writable() is True

    def test_readable(self, pyodide_stderr: PyodideStderr) -> None:
        assert pyodide_stderr.readable() is False

    def test_seekable(self, pyodide_stderr: PyodideStderr) -> None:
        assert pyodide_stderr.seekable() is False

    def test_write(
        self, pyodide_stderr: PyodideStderr, pyodide_pipe: Mock
    ) -> None:
        data = "test error"
        pyodide_stderr.write(data)
        assert pyodide_pipe.call_count == 1
        msg_bytes = pyodide_pipe.call_args[0][0]
        msg = json.loads(msg_bytes)
        assert msg["op"] == "cell-op"
        assert msg["cell_id"] == pyodide_stderr.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == data

    def test_writelines(
        self, pyodide_stderr: PyodideStderr, pyodide_pipe: Mock
    ) -> None:
        lines = ["error1\n", "error2\n", "error3\n"]
        pyodide_stderr.writelines(lines)
        assert pyodide_pipe.call_count == 3


class TestPyodideStdin:
    @pytest.mark.parametrize("cancelled", [False, True])
    async def test_ended_reader_releases_next_prompt(
        self, cancelled: bool
    ) -> None:
        messages: asyncio.Queue[KernelMessage] = asyncio.Queue()
        replies: asyncio.Queue[str | InputReply] = asyncio.Queue()
        stream = PyodideStream(messages.put_nowait, replies, cell_id)
        attempt = ExecutionAttempt(cell_id, "input()")
        with attempt.activate():
            first = asyncio.create_task(
                PyodideStdin(stream)._read_input("First", False)
            )
        second = None
        try:
            await asyncio.wait_for(messages.get(), timeout=1)
            second = asyncio.create_task(
                PyodideStdin(stream.copy_for_thread())._read_input(
                    "Second", False
                )
            )
            if cancelled:
                first.cancel()
            else:
                attempt.completed = True
            with pytest.raises(
                asyncio.CancelledError if cancelled else EOFError
            ):
                await asyncio.wait_for(first, timeout=1)
            message = deserialize_kernel_message(
                await asyncio.wait_for(messages.get(), timeout=1)
            )
            assert isinstance(message, CellNotification)
            assert isinstance(message.console, CellOutput)
            assert isinstance(message.console.input_id, str)
            assert message.console.data == "Second"
            replies.put_nowait(InputReply(message.console.input_id, "answer"))
            assert await asyncio.wait_for(second, timeout=1) == "answer"
        finally:
            first.cancel()
            if second is not None:
                second.cancel()
            await asyncio.gather(
                first,
                *([second] if second is not None else []),
                return_exceptions=True,
            )

    def test_writable(self, pyodide_stdin: PyodideStdin) -> None:
        assert pyodide_stdin.writable() is False

    def test_readable(self, pyodide_stdin: PyodideStdin) -> None:
        assert pyodide_stdin.readable() is True

    def test_readline(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str | InputReply],
    ) -> None:
        pyodide_input_queue.put_nowait("test input")
        result = pyodide_stdin.readline()
        assert result == "test input\n"
        assert pyodide_pipe.call_count == 1
        msg_bytes = pyodide_pipe.call_args[0][0]
        msg = json.loads(msg_bytes)
        assert msg["op"] == "cell-op"
        assert msg["cell_id"] == pyodide_stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == ""

    def test_readline_with_prompt(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str | InputReply],
    ) -> None:
        pyodide_input_queue.put_nowait("test input")
        # The _readline_with_prompt primitive returns bare text; the "\n"
        # is only added by readline() for file-protocol consumers.
        result = pyodide_stdin._readline_with_prompt("Enter: ")
        assert result == "test input"
        assert pyodide_pipe.call_count == 1
        msg_bytes = pyodide_pipe.call_args[0][0]
        msg = json.loads(msg_bytes)
        assert msg["op"] == "cell-op"
        assert msg["cell_id"] == pyodide_stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == "Enter: "

    def test_readlines(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str | InputReply],
    ) -> None:
        pyodide_input_queue.put_nowait("hello")
        result = pyodide_stdin.readlines()
        assert result == ["hello\n"]
        assert pyodide_pipe.call_count == 1
        msg_bytes = pyodide_pipe.call_args[0][0]
        msg = json.loads(msg_bytes)
        assert msg["op"] == "cell-op"
        assert msg["cell_id"] == pyodide_stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == ""

    def test_readline_empty_submission(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_input_queue: asyncio.Queue[str | InputReply],
    ) -> None:
        # Empty submission must be a blank line ("\n"), not "" (= EOF).
        pyodide_input_queue.put_nowait("")
        assert pyodide_stdin.readline() == "\n"
