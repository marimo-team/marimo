# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import click

from marimo._cli.session.exec_cmd import exec_cmd
from marimo._cli.session.list_cmd import list_sessions


@click.group(
    hidden=True,
    help="[Experimental] Interact with running marimo sessions. This API is not stable and may change without notice.",
)
def session() -> None:
    pass


session.add_command(list_sessions)
session.add_command(exec_cmd)

__all__ = ["session"]
