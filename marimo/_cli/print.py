# Copyright 2026 Marimo. All rights reserved.
#
# NB: Do not import click top-level. This module is imported in WASM, which
# does not have access to click.

from __future__ import annotations

import os
import sys
from typing import Any, Protocol, cast

from marimo._config.settings import GLOBAL_SETTINGS


# Check if we're on Windows and if ANSI colors are supported
def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") == "1":
        return False

    # Windows 10 build 14931+ supports ANSI color codes
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # Get Windows version
            major = sys.getwindowsversion().major  # type: ignore[attr-defined]
            build = sys.getwindowsversion().build  # type: ignore[attr-defined]

            # Check if Windows 10+ and if VIRTUAL_TERMINAL_PROCESSING is enabled
            return cast(
                bool,
                major >= 10
                and build >= 14931
                and kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7),  # type: ignore[attr-defined]
            )
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_USE_COLOR = _supports_color()


_ANSI_COLORS = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "bright_black": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
}


class _StyleFn(Protocol):
    def __call__(
        self,
        text: str,
        *,
        fg: str | None = ...,
        bold: bool = ...,
        dim: bool = ...,
    ) -> str: ...


def _ansi_style(
    text: str,
    *,
    fg: str | None = None,
    bold: bool = False,
    dim: bool = False,
) -> str:
    """Minimal ANSI fallback for environments without click (e.g. WASM)."""
    codes: list[int] = []
    if fg and fg in _ANSI_COLORS:
        codes.append(_ANSI_COLORS[fg])
    if bold:
        codes.append(1)
    if dim:
        codes.append(2)
    if not codes:
        return text
    return f"\033[{';'.join(str(c) for c in codes)}m{text}\033[0m"


def _noop_style(
    text: str,
    *,
    fg: str | None = None,
    bold: bool = False,
    dim: bool = False,
) -> str:
    del fg, bold, dim
    return text


def _resolve_style() -> _StyleFn:
    if not _USE_COLOR:
        return _noop_style
    try:
        import click

        return click.style
    except ModuleNotFoundError:
        return _ansi_style


_style: _StyleFn = _resolve_style()


def bold(text: str) -> str:
    return _style(text, bold=True)


def green(text: str, bold: bool = False) -> str:
    return _style(text, fg="green", bold=bold)


def bright_green(text: str, bold: bool = False) -> str:
    return _style(text, fg="bright_green", bold=bold)


def yellow(text: str, bold: bool = False) -> str:
    return _style(text, fg="yellow", bold=bold)


def orange(text: str, bold: bool = False) -> str:
    return _style(text, fg="yellow", bold=bold)


def red(text: str, bold: bool = False) -> str:
    return _style(text, fg="red", bold=bold)


def cyan(text: str, bold: bool = False) -> str:
    return _style(text, fg="bright_blue", bold=bold)


def light_blue(text: str, bold: bool = False) -> str:
    return _style(text, fg="bright_cyan", bold=bold)


def muted(text: str) -> str:
    return _style(text, fg="white", dim=True)


def _echo_or_print(*args: Any, **kwargs: Any) -> None:
    try:
        import click

        click.echo(*args, **kwargs)
    except ModuleNotFoundError:
        print(*args, **kwargs)  # noqa: T201


def echo(*args: Any, **kwargs: Any) -> None:
    if GLOBAL_SETTINGS.QUIET:
        return

    try:
        _echo_or_print(*args, **kwargs)
    except UnicodeEncodeError:
        # Handle non-UTF-8 terminals (such as CP-1252, Windows) by replacing
        # common Unicode characters with ASCII equivalents for non-UTF-8
        # terminals.
        ascii_args = []
        for arg in args:
            if isinstance(arg, str):
                ascii_arg = arg.replace("→", "->").replace("←", "<-")
                ascii_arg = ascii_arg.replace("✓", "v").replace("✗", "x")
                ascii_arg = ascii_arg.replace("•", "*").replace("…", "...")
                ascii_args.append(ascii_arg)
            else:
                ascii_args.append(arg)
        _echo_or_print(*ascii_args, **kwargs)
