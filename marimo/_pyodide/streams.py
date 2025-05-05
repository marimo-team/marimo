# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any, Callable, Optional

from marimo import _loggers
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.mimetypes import ConsoleMimeType
from marimo._messaging.ops import CellOp
from marimo._messaging.streams import std_stream_max_bytes
from marimo._messaging.types import (
    KernelMessage,
    Stderr,
    Stdin,
    Stdout,
    Stream,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterable

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

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        assert self.stream.cell_id is not None
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
        CellOp(
            cell_id=self.stream.cell_id,
            console=CellOutput.stdout(data, mimetype),
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

    def _write_with_mimetype(
        self, data: str, mimetype: ConsoleMimeType
    ) -> int:
        assert self.stream.cell_id is not None
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

        CellOp(
            cell_id=self.stream.cell_id,
            console=CellOutput.stderr(data, mimetype),
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
                f"prompt must be a str, not {type(prompt).__name__}"
            )
        max_bytes = std_stream_max_bytes()
        if sys.getsizeof(prompt) > max_bytes:
            prompt = (
                "Warning: marimo truncated a very large console output.\n"
                + prompt[: int(max_bytes)]
                + " ... "
            )

        CellOp(
            cell_id=self.stream.cell_id,
            console=CellOutput.stdin(prompt),
        ).broadcast(self.stream)

        return self._get_response()

    def _get_response(self) -> str:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.stream.input_queue.get())

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
