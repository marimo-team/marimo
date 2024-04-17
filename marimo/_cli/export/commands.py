# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from pathlib import Path

import click

from marimo._cli.print import green
from marimo._server.export.utils import run_app_then_export_as_html
from marimo._utils.file_watcher import FileWatcher
from marimo._utils.paths import maybe_make_dirs


@click.group(help="""Export a notebook to various formats.""")
def export() -> None:
    pass


@click.command(
    help="""Run a notebook and export it as an HTML file.

Example:

  \b
  * marimo export html notebook.py -o notebook.html
"""
)
@click.option(
    "--include-code/--no-include-code",
    default=True,
    show_default=True,
    type=bool,
    help="Include notebook code in the exported HTML file.",
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help="""
    Watch notebook for changes and regenerate HTML on modification.
    If watchdog is installed, it will be used to watch the file.
    Otherwise, file watcher will poll the file every 1s.
    """,
)
@click.option(
    "-o",
    "--output",
    type=str,
    default=None,
    help="""
    Output file to save the HTML to.
    If not provided, the HTML will be printed to stdout.
    """,
)
@click.argument("name", required=True)
def html(
    name: str,
    include_code: bool,
    output: str,
    watch: bool,
) -> None:
    """
    Run a notebook and export it as an HTML file.
    """
    if watch and not output:
        raise click.UsageError(
            "Cannot use --watch without providing "
            + "an output file with --output."
        )

    def write_html(html: str) -> None:
        if output:
            # Make dirs if needed
            maybe_make_dirs(output)
            with open(output, "w") as f:
                f.write(html)
                f.close()
        else:
            click.echo(html)

    # No watch, just run once
    if not watch:
        (html, _filename) = asyncio.run(
            run_app_then_export_as_html(name, include_code=include_code)
        )
        write_html(html)
        return

    async def on_file_changed(file_path: Path) -> None:
        click.echo(
            f"File {str(file_path)} changed. Re-exporting to {green(output)}"
        )
        (html, _filename) = await run_app_then_export_as_html(
            str(file_path), include_code=include_code
        )
        write_html(html)

    async def start() -> None:
        # Watch the file for changes
        watcher = FileWatcher.create(Path(name), on_file_changed)
        click.echo(f"Watching {green(name)} for changes...")
        watcher.start()
        try:
            # Run forever
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()

    asyncio.run(start())


export.add_command(html)
