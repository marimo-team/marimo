# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

# use spaces instead of a tab to play well with carriage returns;
# \r\t doesn't appear to overwrite characters at the start of a line,
# but \r{TAB} does ...
TAB = "        "


def print_tabbed(string: str, n_tabs: int = 1) -> None:
    print_(f"{TAB * n_tabs}{string}")


def print_(*args: Any, **kwargs: Any) -> None:
    try:
        import click

        click.echo(*args, **kwargs)
    except ImportError:
        print(*args, **kwargs)  # noqa: T201
