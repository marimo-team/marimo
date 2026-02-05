# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import click

from marimo._cli.print import get_colored_group_class
from marimo._cli.tools.thumbnails import thumbnails


@click.group(cls=get_colored_group_class(), help="Utilities for marimo notebooks.")
def tools() -> None:
    pass


tools.add_command(thumbnails)
