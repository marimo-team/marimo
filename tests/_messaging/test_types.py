# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.types import (
    KernelMessage,
    NoopStream,
    Stderr,
    Stdin,
    Stdout,
)


class TestStream:
    def test_noop_stream(self) -> None:
        # Test that NoopStream implements Stream
        stream = NoopStream()

        # Should not raise any exceptions
        stream.write({"key": "value"})
        stream.stop()

        # cell_id should be None by default
        assert stream.cell_id is None

        # Set cell_id
        stream.cell_id = "test_cell"
        assert stream.cell_id == "test_cell"


class TestStdoutStderr:
    class MockStdout(Stdout):
        def __init__(self) -> None:
            self.written_data: list[tuple[str, KnownMimeType]] = []

        def _write_with_mimetype(
            self, data: str, mimetype: KnownMimeType
        ) -> int:
            self.written_data.append((data, mimetype))
            return len(data)

    class MockStderr(Stderr):
        def __init__(self) -> None:
            self.written_data: list[tuple[str, KnownMimeType]] = []

        def _write_with_mimetype(
            self, data: str, mimetype: KnownMimeType
        ) -> int:
            self.written_data.append((data, mimetype))
            return len(data)

    def test_stdout_write(self) -> None:
        stdout = self.MockStdout()

        # Test write method
        result = stdout.write("Hello, world!")

        # Should return the length of the string
        assert result == 13

        # Should call _write_with_mimetype with text/plain mimetype
        assert len(stdout.written_data) == 1
        assert stdout.written_data[0] == ("Hello, world!", "text/plain")

    def test_stderr_write(self) -> None:
        stderr = self.MockStderr()

        # Test write method
        result = stderr.write("Error message")

        # Should return the length of the string
        assert result == 13

        # Should call _write_with_mimetype with text/plain mimetype
        assert len(stderr.written_data) == 1
        assert stderr.written_data[0] == ("Error message", "text/plain")

    def test_stdout_coerces_str_subclass(self) -> None:
        stdout = self.MockStdout()

        class StrSubclass(str):
            pass

        msg = StrSubclass("hello")
        msg.extra = {"key": "value"}  # pyright: ignore[reportAttributeAccessIssue]

        result = stdout.write(msg)
        assert result == 5
        data, mimetype = stdout.written_data[0]
        assert data == "hello"
        assert mimetype == "text/plain"
        # The data stored should be a plain str, not the subclass
        assert type(data) is str
        assert not hasattr(data, "extra")

    def test_stderr_coerces_str_subclass(self) -> None:
        stderr = self.MockStderr()

        class StrSubclass(str):
            pass

        msg = StrSubclass("error!")
        msg.record = {"level": "ERROR", "message": "error!"}  # pyright: ignore[reportAttributeAccessIssue]

        result = stderr.write(msg)
        assert result == 6
        data, mimetype = stderr.written_data[0]
        assert data == "error!"
        assert mimetype == "text/plain"
        assert type(data) is str
        assert not hasattr(data, "record")

    def test_plain_str_not_copied(self) -> None:
        stdout = self.MockStdout()
        plain = "hello"
        stdout.write(plain)
        data, _ = stdout.written_data[0]
        # Plain str should pass through without creating a new object
        assert data is plain

    def test_stdout_name(self) -> None:
        stdout = self.MockStdout()
        assert stdout.name == "stdout"

    def test_stderr_name(self) -> None:
        stderr = self.MockStderr()
        assert stderr.name == "stderr"

    def test_not_stoppable(self) -> None:
        stdout = self.MockStdout()
        assert not hasattr(stdout, "stop")
        stderr = self.MockStderr()
        assert not hasattr(stderr, "stop")


class TestStdin:
    def test_stdin_name(self) -> None:
        stdin = Stdin()
        assert stdin.name == "stdin"

    def test_not_stoppable(self) -> None:
        stdin = Stdin()
        assert not hasattr(stdin, "stop")


class TestKernelMessage:
    def test_kernel_message_type(self) -> None:
        # Test that KernelMessage can be used as a type annotation
        def accepts_kernel_message(message: KernelMessage) -> KernelMessage:
            return message

        # Create a valid kernel message
        message: KernelMessage = ("test_op", {"key": "value"})

        assert accepts_kernel_message(message) == message
