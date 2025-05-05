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

cell_id = CellId_t("test-cell-id")


@pytest.fixture
def pyodide_pipe() -> Mock:
    return Mock()


@pytest.fixture
def pyodide_input_queue() -> asyncio.Queue[str]:
    return asyncio.Queue()


@pytest.fixture
def pyodide_(
    pyodide_pipe: Mock,
    pyodide_input_queue: asyncio.Queue[str],
) -> PyodideStream:
    return PyodideStream(pyodide_pipe, pyodide_input_queue, cell_id)


@pytest.fixture
def pyodide_stdout(pyodide_: PyodideStream) -> PyodideStdout:
    return PyodideStdout(pyodide_)


@pytest.fixture
def pyodide_stderr(pyodide_: PyodideStream) -> PyodideStderr:
    return PyodideStderr(pyodide_)


@pytest.fixture
def pyodide_stdin(pyodide_: PyodideStream) -> PyodideStdin:
    stdin = PyodideStdin(pyodide_)
    stdin._get_response = lambda: "test input\n"
    return stdin


class TestPyodideStream:
    def test_write(self, pyodide_: PyodideStream, pyodide_pipe: Mock) -> None:
        op = "test-op"
        data = {"key": "value"}
        pyodide_.write(op, data)
        pyodide_pipe.assert_called_once_with((op, data))


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
        op, msg = pyodide_pipe.call_args[0][0]
        assert op == "cell-op"
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
        op, msg = pyodide_pipe.call_args[0][0]
        assert op == "cell-op"
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
    def test_writable(self, pyodide_stdin: PyodideStdin) -> None:
        assert pyodide_stdin.writable() is False

    def test_readable(self, pyodide_stdin: PyodideStdin) -> None:
        assert pyodide_stdin.readable() is True

    async def test_readline(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str],
    ) -> None:
        # Queue up a response
        await pyodide_input_queue.put("test input\n")
        # Read the line
        result = pyodide_stdin.readline()
        assert result == "test input\n"
        # Verify prompt was sent
        assert pyodide_pipe.call_count == 1
        op, msg = pyodide_pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == pyodide_stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == ""

    async def test_readline_with_prompt(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str],
    ) -> None:
        # Queue up a response
        await pyodide_input_queue.put("test input\n")
        # Read the line with prompt
        result = pyodide_stdin._readline_with_prompt("Enter: ")
        assert result == "test input\n"
        # Verify prompt was sent
        assert pyodide_pipe.call_count == 1
        op, msg = pyodide_pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == pyodide_stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == "Enter: "

    async def test_readlines(
        self,
        pyodide_stdin: PyodideStdin,
        pyodide_pipe: Mock,
        pyodide_input_queue: asyncio.Queue[str],
    ) -> None:
        pyodide_stdin._get_response = Mock(
            return_value="line1\nline2\nline3\n"
        )

        # Queue up a response
        await pyodide_input_queue.put("line1\nline2\nline3\n")
        # Read the lines
        result = pyodide_stdin.readlines()
        assert result == ["line1", "line2", "line3", ""]
        # Verify prompt was sent
        assert pyodide_pipe.call_count == 1
        op, msg = pyodide_pipe.call_args[0][0]
        assert op == "cell-op"
        assert msg["cell_id"] == pyodide_stdin.stream.cell_id
        assert msg["console"]["mimetype"] == "text/plain"
        assert msg["console"]["data"] == ""
