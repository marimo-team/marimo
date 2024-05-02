# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable, Iterable, Optional

from marimo import _loggers
from marimo._ast.cell import CellId_t
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.ops import CellOp
from marimo._messaging.streams import STD_STREAM_MAX_BYTES
from marimo._messaging.types import (
    KernelMessage,
    Stderr,
    Stdin,
    Stdout,
    Stream,
)

LOGGER = _loggers.marimo_logger()


class PyodideStream(Stream):
    """A thread-safe wrapper around a pipe."""

    def __init__(
        self,
        pipe: Callable[[KernelMessage], None],
        input_queue: asyncio.Queue[str],
        cell_id: Optional[CellId_t] = None,
    ):
        self.pipe = pipe
        self.cell_id = cell_id
        self.input_queue = input_queue

    def write(self, op: str, data: dict[Any, Any]) -> None:
        self.pipe((op, data))


class PyodideStdout(Stdout):
    encoding = sys.stdout.encoding
    errors = sys.stdout.errors
    _fileno: int | None = None

    def __init__(self, stream: Stream) -> None:
        self.stream = stream

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def _write_with_mimetype(self, data: str, mimetype: KnownMimeType) -> int:
        assert self.stream.cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                "write() argument must be a str, not %s" % type(data).__name__
            )
        if sys.getsizeof(data) > STD_STREAM_MAX_BYTES:
            sys.stderr.write(
                "Warning: marimo truncated a very large console output.\n"
            )
            data = data[: int(STD_STREAM_MAX_BYTES)] + " ... "
        CellOp(
            cell_id=self.stream.cell_id,
            console=CellOutput(
                channel=CellChannel.STDOUT,
                mimetype=mimetype,
                data=data,
            ),
        ).broadcast(self.stream)
        return len(data)

    # Buffer type not available python < 3.12, hence type ignore
    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override] # noqa: E501
        for line in sequence:
            self.write(line)


class PyodideStderr(Stderr):
    encoding = sys.stderr.encoding
    errors = sys.stderr.errors
    _fileno: int | None = None

    def __init__(self, stream: Stream) -> None:
        self.stream = stream

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def _write_with_mimetype(self, data: str, mimetype: KnownMimeType) -> int:
        assert self.stream.cell_id is not None
        if not isinstance(data, str):
            raise TypeError(
                "write() argument must be a str, not %s" % type(data).__name__
            )
        if sys.getsizeof(data) > STD_STREAM_MAX_BYTES:
            data = (
                "Warning: marimo truncated a very large console output.\n"
                + data[: int(STD_STREAM_MAX_BYTES)]
                + " ... "
            )

        CellOp(
            cell_id=self.stream.cell_id,
            console=CellOutput(
                channel=CellChannel.STDERR,
                mimetype=mimetype,
                data=data,
            ),
        ).broadcast(self.stream)
        return len(data)

    def writelines(self, sequence: Iterable[str]) -> None:  # type: ignore[override] # noqa: E501
        for line in sequence:
            self.write(line)


class PyodideStdin(Stdin):
    encoding = sys.stdin.encoding
    errors = sys.stdin.errors

    def __init__(self, stream: PyodideStream):
        self.stream = stream

    def writable(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def _readline_with_prompt(self, prompt: str = "") -> str:
        """Read input from the standard in stream, with an optional prompt."""
        assert self.stream.cell_id is not None
        if not isinstance(prompt, str):
            raise TypeError(
                "prompt must be a str, not %s" % type(prompt).__name__
            )
        if sys.getsizeof(prompt) > STD_STREAM_MAX_BYTES:
            prompt = (
                "Warning: marimo truncated a very large console output.\n"
                + prompt[: int(STD_STREAM_MAX_BYTES)]
                + " ... "
            )

        CellOp(
            cell_id=self.stream.cell_id,
            console=CellOutput(
                channel=CellChannel.STDIN,
                mimetype="text/plain",
                data=prompt,
            ),
        ).broadcast(self.stream)

        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self.stream.input_queue.get())
        return response

    def readline(self, size: int | None = -1) -> str:  # type: ignore[override]  # noqa: E501
        # size only included for compatibility with sys.stdin.readline API;
        # we don't support it.
        del size
        return self._readline_with_prompt(prompt="")

    def readlines(self, hint: int | None = -1) -> list[str]:  # type: ignore[override]  # noqa: E501
        # Just an alias for readline.
        #
        # hint only included for compatibility with sys.stdin.readlines API;
        # we don't support it.
        del hint
        return self._readline_with_prompt(prompt="").split("\n")
