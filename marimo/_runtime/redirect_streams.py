# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import io
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING

from marimo._messaging.streams import ThreadSafeStream, redirect
from marimo._messaging.thread_local_streams import (
    ThreadLocalStreamProxy,
    clear_thread_local_streams,
    set_thread_local_streams,
)
from marimo._messaging.types import Stderr, Stdin, Stdout, Stream
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator


_STDIN_ALLOWED = ContextVar("stdin_allowed", default=True)


class _EOFStdin(io.StringIO):
    def _readline_with_prompt(
        self, prompt: str = "", password: bool = False
    ) -> str:
        del prompt, password
        raise EOFError("EOF when reading a line")


@contextlib.contextmanager
def stdin_context(allow_stdin: bool) -> Iterator[None]:
    """Give noninteractive commands an empty stdin, including nested cells."""
    if allow_stdin:
        yield
        return
    token = _STDIN_ALLOWED.set(False)
    previous = sys.stdin
    sys.stdin = _EOFStdin()
    try:
        yield
    finally:
        sys.stdin = previous
        _STDIN_ALLOWED.reset(token)


@contextlib.contextmanager
def redirect_streams(
    cell_id: CellId_t,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    stdin: Stdin | None,
) -> Iterator[None]:
    cell_id_old = stream.cell_id

    # Ordinary nested calls share the outer cell's console. Code mode runs
    # real cells inside the scratchpad, each with its own output and pipes.
    if cell_id_old is not None and cell_id_old != SCRATCH_CELL_ID:
        yield
        return

    stream.cell_id = cell_id
    if stdout is None or stderr is None:
        try:
            yield
        finally:
            stream.cell_id = cell_id_old
        return

    if isinstance(sys.stdout, ThreadLocalStreamProxy):
        # In run mode with console redirection enabled, sys.stdout/sys.stderr
        # are already patched to point to an object that forwards read/write.
        #
        # We don't support redirecting file descriptors in run mode.
        # We also don't support sys.stdin redirection.
        if cell_id_old is None:
            set_thread_local_streams(stdout, stderr)
        try:
            yield
        finally:
            if cell_id_old is None:
                clear_thread_local_streams()
            stream.cell_id = cell_id_old
    else:
        # In edit mode, we have one process per notebook, so we can safely
        # replace sys.stdout/sys.stderr and redirect OS streams
        py_stdout = sys.stdout
        py_stderr = sys.stderr
        py_stdin = sys.stdin
        sys.stdout = stdout  # type: ignore
        sys.stderr = stderr  # type: ignore
        if _STDIN_ALLOWED.get():
            sys.stdin = stdin  # type: ignore

        try:
            with (
                stream.own_console()
                if isinstance(stream, ThreadSafeStream)
                else contextlib.nullcontext(),
                redirect(stdout),
                redirect(stderr),
            ):
                yield
        finally:
            sys.stdout = py_stdout
            sys.stderr = py_stderr
            sys.stdin = py_stdin
            stream.cell_id = cell_id_old
