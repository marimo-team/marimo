# Copyright 2026 Marimo. All rights reserved.
"""``marimo dataflow`` CLI subcommands.

These commands surface assets that ship inside the marimo wheel — the
TypeScript client and the agent recipe — so that any environment with
``marimo`` installed can vendor them without a separate download:

    marimo dataflow client > src/dataflow.tsx
    marimo dataflow agent  > AGENT.md
    marimo dataflow agent --path     # filesystem path, for skill loaders

The TypeScript file ships at ``marimo/_dataflow/clients/typescript/`` and
the recipe at ``marimo/_dataflow/clients/AGENT.md``. They are bundled by
the uv build backend along with the rest of the ``marimo`` module.
"""

from __future__ import annotations

import click

from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._utils.paths import marimo_package_path

_CLIENT_PATH = ("_dataflow", "clients", "typescript", "dataflow.tsx")
_AGENT_PATH = ("_dataflow", "clients", "AGENT.md")


def _resolve(*parts: str) -> str:
    path = marimo_package_path()
    for part in parts:
        path = path / part
    return str(path)


@click.group(
    cls=ColoredGroup,
    help=(
        "Bundled assets for building dataflow API clients.\n\n"
        "The dataflow API exposes a marimo notebook as a typed reactive "
        "function over Server-Sent Events. These subcommands print the "
        "TypeScript client and agent-facing recipe that ship inside the "
        "marimo wheel.\n\n"
        "Run ``marimo dataflow agent`` for a complete end-to-end recipe."
    ),
)
def dataflow() -> None:
    """Bundled dataflow client + agent recipe assets."""


@dataflow.command(cls=ColoredCommand)
@click.option(
    "--path",
    "show_path",
    is_flag=True,
    help="Print the filesystem path of the bundled file instead of its contents.",
)
def client(show_path: bool) -> None:
    """Print the bundled TypeScript dataflow client (``dataflow.tsx``).

    Vendor it into your project:

        marimo dataflow client > src/dataflow.tsx
    """
    path = _resolve(*_CLIENT_PATH)
    if show_path:
        click.echo(path)
        return
    with open(path, encoding="utf-8") as f:
        click.echo(f.read(), nl=False)


@dataflow.command(cls=ColoredCommand)
@click.option(
    "--path",
    "show_path",
    is_flag=True,
    help=(
        "Print the filesystem path instead of contents. Useful when "
        "registering this file as a skill in agent runtimes like Claude "
        "Code or Cursor."
    ),
)
def agent(show_path: bool) -> None:
    """Print the dataflow agent recipe (``AGENT.md``).

    Pipe it into your agent's skill folder, or use ``--path`` to register
    the bundled file directly.
    """
    path = _resolve(*_AGENT_PATH)
    if show_path:
        click.echo(path)
        return
    with open(path, encoding="utf-8") as f:
        click.echo(f.read(), nl=False)
