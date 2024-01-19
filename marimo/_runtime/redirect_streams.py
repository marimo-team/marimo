# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import os
import sys
import threading
from typing import Iterator

from marimo._ast.cell import CellId_t
from marimo._messaging.streams import Stderr, Stdin, Stdout, Stream


def forward_os_stream(stream_object: Stdout | Stderr, fd: int) -> None:
    while True:
        data = os.read(fd, 1024)
        if not data:
            break
        stream_object.write(data.decode())


def dup2newfd(fd: int) -> tuple[int, int, int]:
    """Create a pipe, with `fd` at the write end of it.

    Returns
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
    stream.cell_id = cell_id
    if stdout is None or stderr is None:
        try:
            yield
        finally:
            stream.cell_id = None
        return

    # Redirect file descriptors for writable streams (stdout, stderr).
    #
    # All six of these file descriptors will need to be closed later
    stdout_duped, stdout_read_fd, stdout_fd = dup2newfd(sys.stdout.fileno())
    stderr_duped, stderr_read_fd, stderr_fd = dup2newfd(sys.stderr.fileno())

    # redirecting the standard streams in this way appears to have an overhead
    # of ~1-2ms; the following alternatives had high variance, with up to 30ms
    # overhead
    # - reusing the same two threads instead of creating and destroying on
    #   each call; this requires (slow) synchronization with locks
    # - using a multiprocessing ThreadPool
    # - using a concurrent.futures.ThreadPool/ProcessPool
    stdout_thread = threading.Thread(
        target=forward_os_stream, args=(stdout, stdout_read_fd)
    )
    stderr_thread = threading.Thread(
        target=forward_os_stream, args=(stderr, stderr_read_fd)
    )

    # NB: Python doesn't allow monkey patching methods builtins, so
    # we replace these streams outright
    py_stdout = sys.stdout
    py_stderr = sys.stderr
    py_stdin = sys.stdin
    sys.stdout = stdout  # type: ignore
    sys.stderr = stderr  # type: ignore
    sys.stdin = stdin  # type: ignore

    stdout_thread.start()
    stderr_thread.start()

    try:
        yield
    finally:
        # Restore the original std file descriptors: point stdout_fd and
        # stderr_fd to their original locations. Before this call, stdout_fd
        # and stderr_fd are referring to write ends of pipes. dup2 will
        # close these fds before reusing them, which ensures that the
        # forwarding stdout_thread and stderr_threads will terminate.
        os.dup2(stdout_duped, stdout_fd)
        os.dup2(stderr_duped, stderr_fd)

        stdout_thread.join()
        stderr_thread.join()

        # Close these descriptors, since the std file descriptors have been
        # restored.
        os.close(stdout_duped)
        os.close(stderr_duped)

        # Close the read ends of the pipes
        os.close(stdout_read_fd)
        os.close(stderr_read_fd)

        # Restore Python stdout/stderr/stdin
        sys.stdout = py_stdout
        sys.stderr = py_stderr
        sys.stdin = py_stdin

        stream.cell_id = None
