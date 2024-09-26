# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import importlib.util
from typing import TYPE_CHECKING, Callable

import click

from marimo._cli.parse_args import parse_args
from marimo._cli.print import echo, green
from marimo._server.export import (
    export_as_ipynb,
    export_as_md,
    export_as_script,
    run_app_then_export_as_html,
)
from marimo._server.utils import asyncio_run
from marimo._utils.file_watcher import FileWatcher
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import maybe_make_dirs

if TYPE_CHECKING:
    from pathlib import Path


@click.group(help="""Export a notebook to various formats.""")
def export() -> None:
    pass


def watch_and_export(
    marimo_path: MarimoPath,
    output: str,
    watch: bool,
    export_callback: Callable[[MarimoPath], str],
) -> None:
    if watch and not output:
        raise click.UsageError(
            "Cannot use --watch without providing "
            + "an output file with --output."
        )

    def write_data(data: str) -> None:
        if output:
            # Make dirs if needed
            maybe_make_dirs(output)
            with open(output, "w") as f:
                f.write(data)
                f.close()
        else:
            echo(data)
        return

    # No watch, just run once
    if not watch:
        data = export_callback(marimo_path)
        write_data(data)
        return

    async def on_file_changed(file_path: Path) -> None:
        echo(f"File {str(file_path)} changed. Re-exporting to {green(output)}")
        data = export_callback(MarimoPath(file_path))
        write_data(data)

    async def start() -> None:
        # Watch the file for changes
        watcher = FileWatcher.create(marimo_path.path, on_file_changed)
        echo(f"Watching {green(marimo_path.relative_name)} for changes...")
        watcher.start()
        try:
            # Run forever
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()

    asyncio_run(start())


@click.command(
    help="""Run a notebook and export it as an HTML file.

Example:

  \b
  * marimo export html notebook.py -o notebook.html

Optionally pass CLI args to the notebook:

  \b
  * marimo export html notebook.py -o notebook.html -- -arg1 foo -arg2 bar
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
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def html(
    name: str,
    include_code: bool,
    output: str,
    watch: bool,
    args: tuple[str],
) -> None:
    """
    Run a notebook and export it as an HTML file.
    """

    cli_args = parse_args(args)

    def export_callback(file_path: MarimoPath) -> str:
        (html, _filename) = asyncio_run(
            run_app_then_export_as_html(
                file_path, include_code=include_code, cli_args=cli_args
            )
        )
        return html

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""
Export a marimo notebook as a flat script, in topological order.

Example:

    \b
    * marimo export script notebook.py -o notebook.script.py

Watch for changes and regenerate the script on modification:

    \b
    * marimo export script notebook.py -o notebook.script.py --watch
"""
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help="""
    Watch notebook for changes and regenerate the script on modification.
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
    Output file to save the script to.
    If not provided, the script will be printed to stdout.
    """,
)
@click.argument("name", required=True)
def script(
    name: str,
    output: str,
    watch: bool,
) -> None:
    """
    Export a marimo notebook as a flat script, in topological order.
    """

    def export_callback(file_path: MarimoPath) -> str:
        return export_as_script(file_path)[0]

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""
Export a marimo notebook as a code fenced Markdown file.

Example:

    \b
    * marimo export md notebook.py -o notebook.md

Watch for changes and regenerate the script on modification:

    \b
    * marimo export md notebook.py -o notebook.md --watch
"""
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help="""
    Watch notebook for changes and regenerate the script on modification.
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
    Output file to save the script to.
    If not provided, markdown will be printed to stdout.
    """,
)
@click.argument("name", required=True)
def md(
    name: str,
    output: str,
    watch: bool,
) -> None:
    """
    Export a marimo notebook as a code fenced markdown document.
    """

    def export_callback(file_path: MarimoPath) -> str:
        return export_as_md(file_path)[0]

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""
Export a marimo notebook as a Jupyter notebook in topological order.

Example:

    \b
    * marimo export ipynb notebook.py -o notebook.ipynb

Watch for changes and regenerate the script on modification:

    \b
    * marimo export ipynb notebook.py -o notebook.ipynb --watch

Requires nbformat to be installed.
"""
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help="""
    Watch notebook for changes and regenerate the ipynb on modification.
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
    Output file to save the ipynb file to. If not provided, the ipynb contents
    will be printed to stdout.
    """,
)
@click.argument("name", required=True)
def ipynb(
    name: str,
    output: str,
    watch: bool,
) -> None:
    """
    Export a marimo notebook as a Jupyter notebook in topological order.
    """

    def export_callback(file_path: MarimoPath) -> str:
        return export_as_ipynb(file_path)[0]

    if importlib.util.find_spec("nbformat") is None:
        raise ModuleNotFoundError(
            "Install `nbformat` from PyPI to use marimo export ipynb"
        )
    return watch_and_export(MarimoPath(name), output, watch, export_callback)


export.add_command(html)
export.add_command(script)
export.add_command(md)
export.add_command(ipynb)
