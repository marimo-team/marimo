# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from marimo._cli.print import echo


def _stream(encoding: str) -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding)


def _read(stream: io.TextIOWrapper) -> str:
    stream.flush()
    raw: bytes = stream.buffer.getvalue()  # type: ignore[attr-defined]
    return raw.decode(stream.encoding, errors="replace")


def test_echo_utf8_stream_is_unchanged() -> None:
    stream = _stream("utf-8")
    with redirect_stdout(stream):
        echo("✓ done → (−2,4%)")
    assert _read(stream) == "✓ done → (−2,4%)\n"


def test_echo_replaces_known_characters_on_cp1252() -> None:
    stream = _stream("cp1252")
    with redirect_stdout(stream):
        echo("✓ done → next • item…")
    assert _read(stream) == "v done -> next * item...\n"


def test_echo_does_not_crash_on_arbitrary_characters() -> None:
    # Regression test: a converted notebook containing U+2212 (minus sign)
    # used to raise UnicodeEncodeError from inside the fallback itself.
    stream = _stream("cp1252")
    with redirect_stdout(stream):
        echo("IC -2,3 a -1,4; (−2,4%) → ok")
    assert _read(stream) == "IC -2,3 a -1,4; (\\u22122,4%) -> ok\n"


def test_echo_fallback_uses_explicit_file_encoding() -> None:
    stream = _stream("ascii")
    echo("café ✓", file=stream)
    assert _read(stream) == "caf\\xe9 v\n"


def test_echo_fallback_uses_stderr_encoding() -> None:
    stream = _stream("cp1252")
    with redirect_stderr(stream):
        echo("− err", err=True)
    assert _read(stream) == "\\u2212 err\n"
