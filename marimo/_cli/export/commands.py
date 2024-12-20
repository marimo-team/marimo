# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Callable, Literal, Optional

import click

from marimo._cli.parse_args import parse_args
from marimo._cli.print import echo, green
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.export import (
    ExportResult,
    export_as_ipynb,
    export_as_md,
    export_as_script,
    export_as_wasm,
    run_app_then_export_as_html,
    run_app_then_export_as_ipynb,
)
from marimo._server.export.exporter import Exporter
from marimo._server.utils import asyncio_run
from marimo._utils.file_watcher import FileWatcher
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import maybe_make_dirs

if TYPE_CHECKING:
    from pathlib import Path

_watch_message = (
    "Watch notebook for changes and regenerate the output on modification. "
    "If watchdog is installed, it will be used to watch the file. "
    "Otherwise, file watcher will poll the file every 1s."
)


@click.group(help="""Export a notebook to various formats.""")
def export() -> None:
    pass


def watch_and_export(
    marimo_path: MarimoPath,
    output: Optional[str],
    watch: bool,
    export_callback: Callable[[MarimoPath], ExportResult],
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
            with open(output, "w", encoding="utf-8") as f:
                f.write(data)
                f.close()
        else:
            echo(data)
        return

    # No watch, just run once
    if not watch:
        result = export_callback(marimo_path)
        write_data(result.contents)
        if result.did_error:
            raise click.ClickException(
                "Export was successful, but some cells failed to execute."
            )
        return

    async def on_file_changed(file_path: Path) -> None:
        if output:
            echo(
                f"File {str(file_path)} changed. Re-exporting to {green(output)}"
            )
        result = export_callback(MarimoPath(file_path))
        write_data(result.contents)

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

    marimo export html notebook.py -o notebook.html

Optionally pass CLI args to the notebook:

    marimo export html notebook.py -o notebook.html -- -arg1 foo -arg2 bar
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
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Output file to save the HTML to. "
        "If not provided, the HTML will be printed to stdout."
    ),
)
@click.option(
    "--sandbox",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help=(
        "Run the command in an isolated virtual environment using "
        "`uv run --isolated`. Requires `uv`."
    ),
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def html(
    name: str,
    include_code: bool,
    output: str,
    watch: bool,
    sandbox: bool,
    args: tuple[str],
) -> None:
    """Run a notebook and export it as an HTML file."""
    import sys

    from marimo._cli.sandbox import prompt_run_in_sandbox

    if sandbox or prompt_run_in_sandbox(name):
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name)
        return

    cli_args = parse_args(args)

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return asyncio_run(
            run_app_then_export_as_html(
                file_path,
                include_code=include_code,
                cli_args=cli_args,
            )
        )

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""
Export a marimo notebook as a flat script, in topological order.

Example:

    marimo export script notebook.py -o notebook.script.py

Watch for changes and regenerate the script on modification:

    marimo export script notebook.py -o notebook.script.py --watch
"""
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Output file to save the script to. "
        "If not provided, the script will be printed to stdout."
    ),
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def script(
    name: str,
    output: str,
    watch: bool,
) -> None:
    """
    Export a marimo notebook as a flat script, in topological order.
    """

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return export_as_script(file_path)

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""
Export a marimo notebook as a code fenced Markdown file.

Example:

    marimo export md notebook.py -o notebook.md

Watch for changes and regenerate the script on modification:

    marimo export md notebook.py -o notebook.md --watch
"""
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Output file to save the markdown to. "
        "If not provided, markdown will be printed to stdout."
    ),
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def md(
    name: str,
    output: str,
    watch: bool,
) -> None:
    """
    Export a marimo notebook as a code fenced markdown document.
    """

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return export_as_md(file_path)

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""
Export a marimo notebook as a Jupyter notebook in topological order.

Example:

    marimo export ipynb notebook.py -o notebook.ipynb

Watch for changes and regenerate the script on modification:

    marimo export ipynb notebook.py -o notebook.ipynb --watch

Requires nbformat to be installed.
"""
)
@click.option(
    "--sort",
    type=click.Choice(["top-down", "topological"]),
    default="topological",
    help="Sort cells top-down or in topological order.",
    show_default=True,
)
@click.option(
    "--watch/--no-watch",
    default=False,
    show_default=True,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Output file to save the ipynb file to. "
        "If not provided, the ipynb contents will be printed to stdout."
    ),
)
@click.option(
    "--include-outputs/--no-include-outputs",
    default=False,
    show_default=True,
    type=bool,
    help="Run the notebook and include outputs in the exported ipynb file.",
)
@click.option(
    "--sandbox",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help=(
        "Run the command in an isolated virtual environment using "
        "`uv run --isolated`. Requires `uv`."
    ),
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def ipynb(
    name: str,
    output: str,
    watch: bool,
    sort: Literal["top-down", "topological"],
    include_outputs: bool,
    sandbox: bool,
) -> None:
    """
    Export a marimo notebook as a Jupyter notebook in topological order.
    """
    DependencyManager.nbformat.require(
        why="to convert marimo notebooks to ipynb"
    )

    import sys

    from marimo._cli.sandbox import prompt_run_in_sandbox

    if include_outputs and (sandbox or prompt_run_in_sandbox(name)):
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name)
        return

    def export_callback(file_path: MarimoPath) -> ExportResult:
        if include_outputs:
            return asyncio_run(
                run_app_then_export_as_ipynb(
                    file_path, sort_mode=sort, cli_args={}
                )
            )
        return export_as_ipynb(file_path, sort_mode=sort)

    return watch_and_export(MarimoPath(name), output, watch, export_callback)


@click.command(
    help="""Export a notebook as a WASM-powered standalone HTML file.

Example:

    marimo export html-wasm notebook.py -o notebook.wasm.html

The exported HTML file will run the notebook using WebAssembly, making it
completely self-contained and executable in the browser. This lets you
share interactive notebooks on the web without setting up
infrastructure to run Python code.

The exported notebook runs using Pyodide, which supports most
but not all Python packages. To learn more, see the Pyodide
documentation.

In order for this file to be able to run, it must be served over HTTP,
and cannot be opened directly from the file system (e.g. file://).
"""
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=True,
    help="Output directory to save the HTML to.",
)
@click.option(
    "--mode",
    type=click.Choice(["edit", "run"]),
    default="run",
    help="Whether the notebook code should be editable or readonly",
    show_default=True,
    required=True,
)
@click.option(
    "--show-code/--no-show-code",
    default=True,
    show_default=True,
    help="Whether to show code by default in the exported HTML file.",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def html_wasm(
    name: str,
    output: str,
    mode: Literal["edit", "run"],
    show_code: bool,
) -> None:
    """Export a notebook as a WASM-powered standalone HTML file."""
    out_dir = output
    filename = "index.html"
    ignore_index_html = False
    # If ends with .html, get the directory
    if output.endswith(".html"):
        out_dir = os.path.dirname(output)
        filename = os.path.basename(output)
        ignore_index_html = True

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return export_as_wasm(file_path, mode, show_code=show_code)

    # Export assets first
    Exporter().export_assets(out_dir, ignore_index_html=ignore_index_html)
    echo(
        f"Assets copied to {green(out_dir)}. These assets are required for the "
        "notebook to run in the browser."
    )

    echo(
        "To run the exported notebook, use:\n"
        f"  python -m http.server --directory {out_dir}\n"
        "Then open the URL that is printed to your terminal."
    )

    outfile = os.path.join(out_dir, filename)
    return watch_and_export(MarimoPath(name), outfile, False, export_callback)


export.add_command(html)
export.add_command(script)
export.add_command(md)
export.add_command(ipynb)
export.add_command(html_wasm)
