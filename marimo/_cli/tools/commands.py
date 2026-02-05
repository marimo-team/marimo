# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import click

from marimo._cli.tools.thumbnails import thumbnails


@click.group(help="Utilities for marimo notebooks.")
def tools() -> None:
    pass


tools.add_command(thumbnails)
