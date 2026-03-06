# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json

import click


@click.command(name="list", help="List running marimo sessions.")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output as JSON.",
)
def list_sessions(as_json: bool) -> None:
    from marimo._server.session_registry import SessionRegistryReader

    entries = SessionRegistryReader.read_all()

    if as_json:
        from dataclasses import asdict

        data = [asdict(e) for e in entries]
        # Redact auth tokens in output
        for d in data:
            d.pop("auth_token", None)
        click.echo(json.dumps(data, indent=2))
        return

    if not entries:
        click.echo("No running marimo sessions found.")
        return

    # Table output
    headers = ["SERVER", "NOTEBOOK", "MODE", "PID", "PORT"]
    rows = []
    for e in entries:
        rows.append(
            [
                e.server_id,
                e.notebook_path or "(multi/new)",
                e.mode,
                str(e.pid),
                str(e.port),
            ]
        )

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    # Print header
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    click.echo(header_line)
    click.echo("  ".join("-" * w for w in widths))

    # Print rows
    for row in rows:
        click.echo(
            "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        )
