# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import io
import sys
from typing import TYPE_CHECKING

from marimo._plugins.stateless.plain_text import plain_text
from marimo._runtime.output import _output

if TYPE_CHECKING:
    from collections.abc import Iterator


def _is_proxy(stream: object) -> bool:
    from marimo._messaging.streams import _ThreadLocalStreamProxy

    return isinstance(stream, _ThreadLocalStreamProxy)


@contextlib.contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    """Capture standard output.

    Use this context manager to capture print statements and
    other output sent to standard output.

    Examples:
        ```python
        with mo.capture_stdout() as buffer:
            print("Hello!")
        output = buffer.getvalue()
        ```
    """
    proxy = sys.stdout
    if _is_proxy(proxy):
        # Temporarily swap the thread-local stream to a StringIO so that
        # writes from this thread are captured while other threads are
        # unaffected.
        buffer = io.StringIO()
        old = proxy._get_stream()  # type: ignore[union-attr]
        proxy._set_stream(buffer)  # type: ignore[union-attr]
        try:
            yield buffer
        finally:
            proxy._set_stream(old)  # type: ignore[union-attr]
    else:
        with contextlib.redirect_stdout(io.StringIO()) as buffer:
            yield buffer


@contextlib.contextmanager
def capture_stderr() -> Iterator[io.StringIO]:
    """Capture standard error.

    Use this context manager to capture output sent to standard error.

    Examples:
        ```python
        with mo.capture_stderr() as buffer:
            sys.stderr.write("Hello!")
        output = buffer.getvalue()
        ```
    """
    proxy = sys.stderr
    if _is_proxy(proxy):
        buffer = io.StringIO()
        old = proxy._get_stream()  # type: ignore[union-attr]
        proxy._set_stream(buffer)  # type: ignore[union-attr]
        try:
            yield buffer
        finally:
            proxy._set_stream(old)  # type: ignore[union-attr]
    else:
        with contextlib.redirect_stderr(io.StringIO()) as buffer:
            yield buffer


def _redirect(msg: str) -> None:
    _output.append(plain_text(msg))


@contextlib.contextmanager
def redirect_stdout() -> Iterator[None]:
    """Redirect stdout to a cell's output area.

    Examples:
        ```python
        with mo.redirect_stdout():
            # These print statements will show up in the cell's output area
            print("Hello!")
            print("World!")
        ```
    """
    proxy = sys.stdout
    if _is_proxy(proxy):
        stream = proxy._get_stream()  # type: ignore[union-attr]
        old_write = stream.write
        stream.write = _redirect  # type: ignore[assignment]
        try:
            yield
        finally:
            stream.write = old_write  # type: ignore[assignment]
    else:
        old_stdout_write = sys.stdout.write
        sys.stdout.write = _redirect  # type: ignore
        try:
            yield
        finally:
            sys.stdout.write = old_stdout_write  # type: ignore


@contextlib.contextmanager
def redirect_stderr() -> Iterator[None]:
    """Redirect `stderr` to a cell's output area.

    Examples:
        ```python
        with mo.redirect_stderr():
            # These messages will show up in the cell's output area
            sys.stderr.write("Hello!")
            sys.stderr.write("World!")
        ```
    """
    proxy = sys.stderr
    if _is_proxy(proxy):
        stream = proxy._get_stream()  # type: ignore[union-attr]
        old_write = stream.write
        stream.write = _redirect  # type: ignore[assignment]
        try:
            yield
        finally:
            stream.write = old_write  # type: ignore[assignment]
    else:
        old_stderr_write = sys.stderr.write
        sys.stderr.write = _redirect  # type: ignore
        try:
            yield
        finally:
            sys.stderr.write = old_stderr_write  # type: ignore
