import asyncio
from unittest.mock import Mock

import pytest

from marimo._pyodide.streams import (
    PyodideStderr,
    PyodideStdin,
    PyodideStdout,
    PyodideStream,
)
from marimo._types.ids import CellId_t


@pytest.fixture
def cell_id() -> CellId_t:
    return CellId_t("test-cell-id")


@pytest.fixture
def pipe() -> Mock:
    return Mock()


@pytest.fixture
def input_queue() -> asyncio.Queue[str]:
    return asyncio.Queue()


@pytest.fixture
def stream(
    pipe: Mock, input_queue: asyncio.Queue[str], cell_id: CellId_t
) -> PyodideStream:
    return PyodideStream(pipe, input_queue, cell_id)


@pytest.fixture
def stdout(stream: PyodideStream) -> PyodideStdout:
    return PyodideStdout(stream)


@pytest.fixture
def stderr(stream: PyodideStream) -> PyodideStderr:
    return PyodideStderr(stream)


@pytest.fixture
def stdin(stream: PyodideStream) -> PyodideStdin:
    stdin = PyodideStdin(stream)
    stdin._get_response = lambda: "test input\n"
    return stdin


class TestPyodideStream:
    def test_write(self, stream: PyodideStream, pipe: Mock) -> None:
        op = "test-op"
        data = {"key": "value"}
        stream.write(op, data)
        pipe.assert_called_once_with((op, data))


class TestPyodideStdout:
    def test_writable(self, stdout: PyodideStdout) -> None:
        assert stdout.writable() is True

    def test_readable(self, stdout: PyodideStdout) -> None:
        assert stdout.readable() is False

    def test_seekable(self, stdout: PyodideStdout) -> None:
        assert stdout.seekable() is False

    def test_write(self, stdout: PyodideStdout, pipe: Mock) -> None:
        data = "test output"
        stdout.write(data)
        assert pipe.call_count == 1
        op, msg = pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == stdout.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == data

    def test_writelines(self, stdout: PyodideStdout, pipe: Mock) -> None:
        lines = ["line1\n", "line2\n", "line3\n"]
        stdout.writelines(lines)
        assert pipe.call_count == 3


class TestPyodideStderr:
    def test_writable(self, stderr: PyodideStderr) -> None:
        assert stderr.writable() is True

    def test_readable(self, stderr: PyodideStderr) -> None:
        assert stderr.readable() is False

    def test_seekable(self, stderr: PyodideStderr) -> None:
        assert stderr.seekable() is False

    def test_write(self, stderr: PyodideStderr, pipe: Mock) -> None:
        data = "test error"
        stderr.write(data)
        assert pipe.call_count == 1
        op, msg = pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == stderr.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == data

    def test_writelines(self, stderr: PyodideStderr, pipe: Mock) -> None:
        lines = ["error1\n", "error2\n", "error3\n"]
        stderr.writelines(lines)
        assert pipe.call_count == 3


class TestPyodideStdin:
    def test_writable(self, stdin: PyodideStdin) -> None:
        assert stdin.writable() is False

    def test_readable(self, stdin: PyodideStdin) -> None:
        assert stdin.readable() is True

    async def test_readline(
        self, stdin: PyodideStdin, pipe: Mock, input_queue: asyncio.Queue[str]
    ) -> None:
        # Queue up a response
        await input_queue.put("test input\n")
        # Read the line
        result = stdin.readline()
        assert result == "test input\n"
        # Verify prompt was sent
        assert pipe.call_count == 1
        op, msg = pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == ""

    async def test_readline_with_prompt(
        self, stdin: PyodideStdin, pipe: Mock, input_queue: asyncio.Queue[str]
    ) -> None:
        # Queue up a response
        await input_queue.put("test input\n")
        # Read the line with prompt
        result = stdin._readline_with_prompt("Enter: ")
        assert result == "test input\n"
        # Verify prompt was sent
        assert pipe.call_count == 1
        op, msg = pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == "Enter: "

    async def test_readlines(
        self, stdin: PyodideStdin, pipe: Mock, input_queue: asyncio.Queue[str]
    ) -> None:
        stdin._get_response = Mock(return_value="line1\nline2\nline3\n")

        # Queue up a response
        await input_queue.put("line1\nline2\nline3\n")
        # Read the lines
        result = stdin.readlines()
        assert result == ["line1", "line2", "line3", ""]
        # Verify prompt was sent
        assert pipe.call_count == 1
        op, msg = pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == ""
