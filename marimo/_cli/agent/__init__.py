# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import click

from marimo._cli.agent.exec_cmd import exec_cmd
from marimo._cli.agent.sessions import sessions


@click.group(
    hidden=True,
    help="[Experimental] Agent-facing commands for interacting with marimo. This API is not stable and may change without notice.",
)
def agent() -> None:
    pass


agent.add_command(sessions)
agent.add_command(exec_cmd)

__all__ = ["agent"]
