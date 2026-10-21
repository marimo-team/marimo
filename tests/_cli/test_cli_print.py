# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import click
import pytest

from marimo._cli import print as cli_print
from marimo._cli.print import echo


def _stream(encoding: str) -> io.TextIOWrapper:
    # newline="\n" disables newline translation, so the assertions below see
    # exactly what echo() wrote on every platform (not "\r\n" on Windows).
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, newline="\n")


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


@pytest.mark.parametrize("use_click", [True, False])
def test_orange_and_yellow_have_distinct_colors(
    monkeypatch: pytest.MonkeyPatch, use_click: bool
) -> None:
    monkeypatch.setattr(
        cli_print,
        "_style",
        click.style if use_click else cli_print._ansi_style,
    )
    reset_bold = "\033[22m" if use_click else ""
    assert cli_print.orange("[Deprecated]") == (
        f"\033[38;5;208m{reset_bold}[Deprecated]\033[0m"
    )
    assert cli_print.yellow("model") == f"\033[33m{reset_bold}model\033[0m"
