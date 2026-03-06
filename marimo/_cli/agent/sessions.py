# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import click

from marimo._cli.agent.list_cmd import list_sessions


@click.group(
    help="Manage running marimo sessions.",
)
def sessions() -> None:
    pass


sessions.add_command(list_sessions)
