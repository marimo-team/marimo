# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import click

from marimo._cli.errors import MarimoCLIMissingDependencyError


@click.command(hidden=True, help="Pair with an AI agent via MCP.")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"]),
    default="stdio",
    help="Transport protocol.",
)
@click.option(
    "--mode",
    type=click.Choice(["tools", "code-mode"]),
    default="code-mode",
    help="MCP server mode.",
)
@click.option(
    "-p",
    "--port",
    type=int,
    default=2718,
    help="Port of running marimo server.",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host of running marimo server.",
)
def pair(transport: str, mode: str, port: int, host: str) -> None:
    from marimo._dependencies.dependencies import DependencyManager
    from marimo._mcp.pair import (
        PairConnectionError,
        pair_http,
        pair_stdio,
    )

    if not DependencyManager.mcp.has():
        raise MarimoCLIMissingDependencyError(
            "The 'mcp' package is required for marimo pair.",
            "marimo[mcp]",
        )

    if transport == "http":
        pair_http(host, port)
    else:
        try:
            pair_stdio(host, port, mcp_mode=mode)
        except PairConnectionError as e:
            click.echo(
                click.style("Error", fg="red", bold=True) + f": {e}",
                err=True,
            )
            sys.exit(1)
