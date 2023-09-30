import contextlib
import io
from typing import Iterator


@contextlib.contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    with contextlib.redirect_stdout(io.StringIO()) as buffer:
        yield buffer


@contextlib.contextmanager
def capture_stderr() -> Iterator[io.StringIO]:
    with contextlib.redirect_stderr(io.StringIO()) as buffer:
        yield buffer
