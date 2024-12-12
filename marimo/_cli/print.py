# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import os
import sys
from typing import Any, cast

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


def bold(text: str) -> str:
    return "\033[1m" + text + "\033[0m" if _USE_COLOR else text


def green(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[32m" if not bold else "\033[1;32m"
    return prefix + text + "\033[0m"


def yellow(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[33m" if not bold else "\033[1;33m"
    return prefix + text + "\033[0m"


def orange(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[33m" if not bold else "\033[1;33m"
    return prefix + text + "\033[0m"


def red(text: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    prefix = "\033[31m" if not bold else "\033[1;31m"
    return prefix + text + "\033[0m"


def muted(text: str) -> str:
    return "\033[90m" + text + "\033[0m" if _USE_COLOR else text


def echo(*args: Any, **kwargs: Any) -> None:
    if GLOBAL_SETTINGS.QUIET:
        return

    try:
        import click

        click.echo(*args, **kwargs)
    except ModuleNotFoundError:
        print(*args, **kwargs)  # noqa: T201
