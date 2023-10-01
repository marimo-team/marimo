# Copyright 2023 Marimo. All rights reserved.
import contextlib
import io
import sys
from typing import Iterator

from marimo._runtime.output import _output


@contextlib.contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    with contextlib.redirect_stdout(io.StringIO()) as buffer:
        yield buffer


@contextlib.contextmanager
def capture_stderr() -> Iterator[io.StringIO]:
    with contextlib.redirect_stderr(io.StringIO()) as buffer:
        yield buffer


@contextlib.contextmanager
def redirect_stdout() -> Iterator[None]:
    old_stdout_write = sys.stdout.write
    sys.stdout.write = lambda msg: _output.append(msg)  # type: ignore
    try:
        yield
    finally:
        sys.stdout.write = old_stdout_write  # type: ignore


@contextlib.contextmanager
def redirect_stderr() -> Iterator[None]:
    old_stderr_write = sys.stderr.write
    sys.stderr.write = lambda msg: _output.append(msg)  # type: ignore
    try:
        yield
    finally:
        sys.stderr.write = old_stderr_write  # type: ignore
