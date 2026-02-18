# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import os
import sys
from typing import TYPE_CHECKING

from marimo._messaging.streams import redirect
from marimo._messaging.thread_local_streams import (
    ThreadLocalStreamProxy,
    clear_thread_local_streams,
    set_thread_local_streams,
)
from marimo._messaging.types import Stderr, Stdin, Stdout, Stream
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator


def forward_os_stream(stream_object: Stdout | Stderr, fd: int) -> None:
    while True:
        data = os.read(fd, 1024)
        if not data:
            break
        stream_object.write(data.decode())


def dup2newfd(fd: int) -> tuple[int, int, int]:
    """Create a pipe, with `fd` at the write end of it.

    Returns:
    - duplicate (os.dup) of `fd`
    - read end of pipe
    - fd (which now points to the file referenced by the write end of the pipe)

    When done with the pipe, the write-end of the pipe should be closed
    and remapped to point to the saved duplicate. The read end should
    also be closed, as should the saved duplicate.
    """
    # fd_dup keeps a pointer to `fd`'s original location
    fd_dup = os.dup(fd)
    # create a pipe, with `fd` as the write end of it
    read_fd, write_fd = os.pipe()
    # repurpose fd to point to the write-end of the pipe
    os.dup2(write_fd, fd)
    os.close(write_fd)
    return fd_dup, read_fd, fd


# Redirect output stream and stdout/stderr/stdin (if they have been installed)
@contextlib.contextmanager
def redirect_streams(
    cell_id: CellId_t,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    stdin: Stdin | None,
) -> Iterator[None]:
    cell_id_old = stream.cell_id

    # In a nested context; NOOP so messages still reach the top-level cell.
    if cell_id_old is not None:
        try:
            yield
        finally:
            ...
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
        set_thread_local_streams(stdout, stderr)
        try:
            yield
        finally:
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
        sys.stdin = stdin  # type: ignore

        try:
            with redirect(stdout), redirect(stderr):
                yield
        finally:
            sys.stdout = py_stdout
            sys.stderr = py_stderr
            sys.stdin = py_stdin
            stream.cell_id = cell_id_old
