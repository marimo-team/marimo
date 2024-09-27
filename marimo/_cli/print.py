# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from typing import Any

from marimo._config.settings import GLOBAL_SETTINGS

# Print helpers


def bold(text: str) -> str:
    return "\033[1m" + text + "\033[0m"


def green(text: str, bold: bool = False) -> str:
    prefix = "\033[32m" if not bold else "\033[1;32m"
    return prefix + text + "\033[0m"


def orange(text: str, bold: bool = False) -> str:
    prefix = "\033[33m" if not bold else "\033[1;33m"
    return prefix + text + "\033[0m"


def red(text: str, bold: bool = False) -> str:
    prefix = "\033[31m" if not bold else "\033[1;31m"
    return prefix + text + "\033[0m"


def echo(*args: Any, **kwargs: Any) -> None:
    import click

    if GLOBAL_SETTINGS.QUIET:
        return

    click.echo(*args, **kwargs)
