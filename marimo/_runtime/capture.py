# Copyright 2023 Marimo. All rights reserved.
import contextlib
import io
import sys
from typing import Iterator

from marimo._plugins.stateless.plain_text import plain_text
from marimo._runtime.output import _output


@contextlib.contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    """Capture standard output.

    Use this context manager to capture print statements and
    other output sent to standard output.

    **Example.**

    ```python
    with mo.capture_stdout() as buffer:
       print("Hello!")
    output = buffer.getvalue()
    ```
    """
    with contextlib.redirect_stdout(io.StringIO()) as buffer:
        yield buffer


@contextlib.contextmanager
def capture_stderr() -> Iterator[io.StringIO]:
    """Capture standard error.

    Use this context manager to capture output sent to standard error.

    **Example.**

    ```python
    with mo.capture_stderr() as buffer:
       sys.stderr.write("Hello!")
    output = buffer.getvalue()
    ```
    """
    with contextlib.redirect_stderr(io.StringIO()) as buffer:
        yield buffer


def _redirect(msg: str) -> None:
    _output.append(plain_text(msg))


@contextlib.contextmanager
def redirect_stdout() -> Iterator[None]:
    """Redirect stdout to a cell's output area.

    ```python
    with mo.redirect_stdout():
        # These print statements will show up in the cell's output area
        print("Hello!")
        print("World!")
    ```
    """
    old_stdout_write = sys.stdout.write
    sys.stdout.write = _redirect  # type: ignore
    try:
        yield
    finally:
        sys.stdout.write = old_stdout_write  # type: ignore


@contextlib.contextmanager
def redirect_stderr() -> Iterator[None]:
    """Redirect `stderr` to a cell's output area.

    ```python
    with mo.redirect_stdout():
        # These messages will show up in the cell's output area
        sys.stderr.write("Hello!")
        sys.stderr.write("World!")
    ```
    """
    old_stderr_write = sys.stderr.write
    sys.stderr.write = _redirect  # type: ignore
    try:
        yield
    finally:
        sys.stderr.write = old_stderr_write  # type: ignore
