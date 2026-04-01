# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

# use spaces instead of a tab to play well with carriage returns;
# \r\t doesn't appear to overwrite characters at the start of a line,
# but \r{TAB} does ...
TAB = "        "


def print_tabbed(string: str, n_tabs: int = 1) -> None:
    """Print a string indented by n_tabs levels using space-based tabs."""
    print_(f"{TAB * n_tabs}{string}")


def print_(*args: Any, **kwargs: Any) -> None:
    """Print using click.echo when available, falling back to the built-in print."""
    try:
        import click

        click.echo(*args, **kwargs)
    except ImportError:
        print(*args, **kwargs)  # noqa: T201
