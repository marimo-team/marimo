# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Literal, Optional

import click

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._cli.export.cloudflare import create_cloudflare_files
from marimo._cli.export.thumbnail import thumbnail
from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.install_hints import get_playwright_chromium_setup_commands
from marimo._cli.parse_args import parse_args
from marimo._cli.print import (
    echo,
    green,
)
from marimo._cli.utils import prompt_to_overwrite
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._server.api.utils import parse_title
from marimo._server.export import (
    ExportResult,
    export_as_ipynb,
    export_as_md,
    export_as_script,
    export_as_wasm,
    run_app_then_export_as_html,
    run_app_then_export_as_ipynb,
    run_app_then_export_as_pdf,
)
from marimo._server.export.exporter import Exporter
from marimo._server.utils import asyncio_run
from marimo._utils.file_watcher import FileWatcher
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import maybe_make_dirs

_watch_message = (
    "Watch notebook for changes and regenerate the output on modification. "
    "If watchdog is installed, it will be used to watch the file. "
    "Otherwise, file watcher will poll the file every 1s."
)

_sandbox_message = (
    "Run the command in an isolated virtual environment using "
    "`uv run --isolated`. Requires `uv`."
)


@click.group(
    cls=ColoredGroup, help="""Export a notebook to various formats."""
)
def export() -> None:
    pass


def watch_and_export(
    marimo_path: MarimoPath,
    output: Optional[Path],
    watch: bool,
    export_callback: Callable[[MarimoPath], ExportResult],
    force: bool,
    *,
    initial_export_in_watch: bool = False,
) -> None:
    if watch and not output:
        raise click.UsageError(
            "Cannot use --watch without providing "
            + "an output file with --output."
        )

    def write_result(result: ExportResult) -> None:
        if output:
            # Make dirs if needed
            maybe_make_dirs(output)
            output.write_bytes(result.bytez)
        else:
            echo(result.text)
        return

    if output:
        output_path = Path(output)
        if not force and not watch:
            if not prompt_to_overwrite(output_path):
                return

    # No watch, just run once
    if not watch:
        result = export_callback(marimo_path)
        write_result(result)
        if result.did_error:
            raise click.ClickException(
                "Export was successful, but some cells failed to execute."
            )
        return

    # Watch mode: optionally do an initial export before waiting for changes
    if initial_export_in_watch:
        result = export_callback(marimo_path)
        write_result(result)
        if result.did_error:
            echo(
                "Warning: Export was successful, but some cells failed to execute.",
                err=True,
            )

    async def on_file_changed(file_path: Path) -> None:
        if output:
            echo(
                f"File {str(file_path)} changed. Re-exporting to {green(str(output))}"
            )
        try:
            # `export_callback` may call `asyncio_run()` internally. This callback
            # runs inside the file watcher's event loop, so we must execute the
            # export in a separate thread to avoid `asyncio.run()` nesting.
            result = await asyncio.to_thread(
                export_callback, MarimoPath(file_path)
            )
        except Exception as e:
            echo(f"Error: {e}", err=True)
            return

        write_result(result)
        if result.did_error:
            echo(
                "Warning: Export was successful, but some cells failed to execute.",
                err=True,
            )

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
    cls=ColoredCommand,
    help="""Run a notebook and export it as an HTML file.

Example:

    marimo export html notebook.py -o notebook.html

Optionally pass CLI args to the notebook:

    marimo export html notebook.py -o notebook.html -- -arg1 foo -arg2 bar
""",
)
@click.option(
    "--include-code/--no-include-code",
    default=True,
    type=bool,
    help="Include notebook code in the exported HTML file.",
)
@click.option(
    "--watch/--no-watch",
    default=False,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output file to save the HTML to. "
        "If not provided, the HTML will be printed to stdout."
    ),
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force overwrite of the output file if it already exists.",
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
    output: Path,
    watch: bool,
    sandbox: Optional[bool],
    force: bool,
    args: tuple[str],
) -> None:
    """Run a notebook and export it as an HTML file."""
    import sys

    # Set default, if not provided
    if sandbox is None:
        from marimo._cli.sandbox import maybe_prompt_run_in_sandbox

        sandbox = maybe_prompt_run_in_sandbox(name)

    if sandbox:
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name=name)
        return

    cli_args = parse_args(args)

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return asyncio_run(
            run_app_then_export_as_html(
                file_path,
                include_code=include_code,
                cli_args=cli_args,
                argv=list(args),
            )
        )

    return watch_and_export(
        MarimoPath(name), output, watch, export_callback, force
    )


@click.command(
    cls=ColoredCommand,
    help="""
Export a marimo notebook as a flat script, in topological order.

Example:

    marimo export script notebook.py -o notebook.script.py

Watch for changes and regenerate the script on modification:

    marimo export script notebook.py -o notebook.script.py --watch
""",
)
@click.option(
    "--watch/--no-watch",
    default=False,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output file to save the script to. "
        "If not provided, the script will be printed to stdout."
    ),
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force overwrite of the output file if it already exists.",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def script(
    name: str, output: Path, watch: bool, sandbox: Optional[bool], force: bool
) -> None:
    """
    Export a marimo notebook as a flat script, in topological order.
    """
    import sys

    # Set default, if not provided
    if sandbox is None:
        from marimo._cli.sandbox import maybe_prompt_run_in_sandbox

        sandbox = maybe_prompt_run_in_sandbox(name)

    if sandbox:
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name=name)
        return

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return export_as_script(file_path)

    return watch_and_export(
        MarimoPath(name), output, watch, export_callback, force
    )


@click.command(
    cls=ColoredCommand,
    help="""
Export a marimo notebook as a code fenced Markdown file.

Example:

    marimo export md notebook.py -o notebook.md

Watch for changes and regenerate the script on modification:

    marimo export md notebook.py -o notebook.md --watch
""",
)
@click.option(
    "--watch/--no-watch",
    default=False,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output file to save the markdown to. "
        "If not provided, markdown will be printed to stdout."
    ),
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force overwrite of the output file if it already exists.",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def md(
    name: str, output: Path, watch: bool, sandbox: Optional[bool], force: bool
) -> None:
    """
    Export a marimo notebook as a code fenced markdown document.
    """
    import sys

    # Set default, if not provided
    if sandbox is None:
        from marimo._cli.sandbox import maybe_prompt_run_in_sandbox

        sandbox = maybe_prompt_run_in_sandbox(name)

    if sandbox:
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name=name)
        return

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return export_as_md(file_path)

    return watch_and_export(
        MarimoPath(name), output, watch, export_callback, force
    )


@click.command(
    cls=ColoredCommand,
    help="""
Export a marimo notebook as a Jupyter notebook in topological order.

Example:

    marimo export ipynb notebook.py -o notebook.ipynb

Watch for changes and regenerate the script on modification:

    marimo export ipynb notebook.py -o notebook.ipynb --watch

Requires nbformat to be installed.
""",
)
@click.option(
    "--sort",
    type=click.Choice(["top-down", "topological"]),
    default="topological",
    help="Sort cells top-down or in topological order.",
)
@click.option(
    "--watch/--no-watch",
    default=False,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output file to save the ipynb file to. "
        "If not provided, the ipynb contents will be printed to stdout."
    ),
)
@click.option(
    "--include-outputs/--no-include-outputs",
    default=False,
    type=bool,
    help="Run the notebook and include outputs in the exported ipynb file.",
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force overwrite of the output file if it already exists.",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def ipynb(
    name: str,
    output: Path,
    watch: bool,
    sort: Literal["top-down", "topological"],
    include_outputs: bool,
    sandbox: Optional[bool],
    force: bool,
) -> None:
    """
    Export a marimo notebook as a Jupyter notebook in topological order.
    """
    import sys

    if include_outputs:
        # Set default, if not provided
        from marimo._cli.sandbox import maybe_prompt_run_in_sandbox

        if sandbox is None:
            sandbox = maybe_prompt_run_in_sandbox(name)

        if sandbox:
            from marimo._cli.sandbox import run_in_sandbox

            run_in_sandbox(
                sys.argv[1:],
                name=name,
                additional_deps=["nbformat"],
            )
            return

    try:
        DependencyManager.nbformat.require(
            why="to convert marimo notebooks to ipynb"
        )
    except ModuleNotFoundError as e:
        package = getattr(e, "name", None) or "nbformat"
        raise MarimoCLIMissingDependencyError(str(e), package) from None

    def export_callback(file_path: MarimoPath) -> ExportResult:
        if include_outputs:
            return asyncio_run(
                run_app_then_export_as_ipynb(
                    file_path,
                    sort_mode=sort,
                    cli_args={},
                    argv=None,
                )
            )
        return export_as_ipynb(file_path, sort_mode=sort)

    return watch_and_export(
        MarimoPath(name), output, watch, export_callback, force
    )


@click.command(
    cls=ColoredCommand,
    help="""Export a marimo notebook as a PDF file.

Example:

    marimo export pdf notebook.py -o notebook.pdf

Optionally pass CLI args to the notebook:

    marimo export pdf notebook.py -o notebook.pdf -- -arg1 foo -arg2 bar

Requires nbformat and nbconvert to be installed.
""",
)
@click.option(
    "--include-outputs/--no-include-outputs",
    default=True,
    type=bool,
    help="Run the notebook and include outputs in the exported PDF file.",
)
@click.option(
    "--include-inputs/--no-include-inputs",
    default=True,
    type=bool,
    help="Include code cell inputs in the exported PDF file.",
)
@click.option(
    "--webpdf/--no-webpdf",
    default=True,
    type=bool,
    help=(
        "Use nbconvert's WebPDF exporter (Chromium). If disabled, marimo will "
        "try standard PDF export (pandoc + TeX) first and fall back to WebPDF."
    ),
)
@click.option(
    "--watch/--no-watch",
    default=False,
    type=bool,
    help=_watch_message,
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output PDF file to save to.",
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force overwrite of the output file if it already exists.",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def pdf(
    name: str,
    output: Path,
    watch: bool,
    include_outputs: bool,
    include_inputs: bool,
    webpdf: bool,
    sandbox: Optional[bool],
    force: bool,
    args: tuple[str],
) -> None:
    """Run a notebook and export it as a PDF file."""
    import sys

    if include_outputs:
        # Set default, if not provided
        if sandbox is None:
            from marimo._cli.sandbox import maybe_prompt_run_in_sandbox

            sandbox = maybe_prompt_run_in_sandbox(name)

        if sandbox:
            from marimo._cli.sandbox import run_in_sandbox

            export_deps = ["nbformat"]
            # Adding webpdf extras to sandbox even if `webpdf` is False, since standard PDF export may fall back to it.
            export_deps.append("nbconvert[webpdf]")
            run_in_sandbox(
                sys.argv[1:],
                name=name,
                additional_deps=export_deps,
            )
            return

    try:
        DependencyManager.require_many(
            "for PDF export",
            DependencyManager.nbformat,
            DependencyManager.nbconvert,
        )
    except ManyModulesNotFoundError as e:
        sandbox_rerun_command = (
            f"marimo export pdf {name} --output {output} --sandbox"
        )
        raise MarimoCLIMissingDependencyError(
            str(e),
            e.package_names,
            followup_commands=sandbox_rerun_command,
            followup_label="Alternative:",
            additional_tip="Requires uv.",
        ) from None

    cli_args = parse_args(args) if include_outputs else {}

    def export_callback(
        file_path: MarimoPath,
    ) -> tuple[bytes | None, bool]:
        try:
            return asyncio_run(
                run_app_then_export_as_pdf(
                    file_path,
                    include_outputs=include_outputs,
                    include_inputs=include_inputs,
                    webpdf=webpdf,
                    cli_args=cli_args,
                    argv=list(args) if include_outputs else None,
                )
            )
        except ModuleNotFoundError as e:
            if getattr(e, "name", None) == "playwright":
                raise MarimoCLIMissingDependencyError(
                    "Playwright is required for WebPDF export.",
                    "nbconvert[webpdf]",
                    followup_commands=get_playwright_chromium_setup_commands(),
                ) from None
            raise
        except Exception as e:
            raise click.ClickException(f"Failed to export PDF: {e}") from None

    def export_callback_impl(file_path: MarimoPath) -> ExportResult:
        pdf_bytes, did_error = export_callback(file_path)
        if pdf_bytes is None:
            raise click.ClickException("Failed to export PDF.")
        return ExportResult(
            contents=pdf_bytes,
            download_filename=str(output),
            did_error=did_error,
        )

    return watch_and_export(
        MarimoPath(name),
        output,
        watch,
        export_callback_impl,
        force,
        initial_export_in_watch=True,
    )


@click.command(
    cls=ColoredCommand,
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
""",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output directory to save the HTML to.",
)
@click.option(
    "--mode",
    type=click.Choice(["edit", "run"]),
    default="run",
    help="Whether the notebook code should be editable or readonly.",
    required=True,
)
@click.option(
    "--watch/--no-watch",
    default=False,
    help=("Whether to watch the original file and export upon change"),
)
@click.option(
    "--show-code/--no-show-code",
    default=False,
    help=(
        "Whether to show code by default in the exported HTML file; "
        "only relevant for run mode."
    ),
)
@click.option(
    "--include-cloudflare/--no-include-cloudflare",
    default=False,
    help=(
        "Whether to include Cloudflare Worker configuration files"
        " (index.js and wrangler.jsonc) for easy deployment."
    ),
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Force overwrite of the output file if it already exists.",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def html_wasm(
    name: str,
    output: Path,
    mode: Literal["edit", "run"],
    watch: bool,
    show_code: bool,
    include_cloudflare: bool,
    sandbox: Optional[bool],
    force: bool,
) -> None:
    """Export a notebook as a WASM-powered standalone HTML file."""
    import sys

    # Set default, if not provided
    if sandbox is None:
        from marimo._cli.sandbox import maybe_prompt_run_in_sandbox

        sandbox = maybe_prompt_run_in_sandbox(name)

    if sandbox:
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name=name)
        return

    out_dir = output
    filename = "index.html"
    ignore_index_html = False
    # If ends with .html, get the directory
    if output.suffix == ".html":
        out_dir = output.parent
        filename = output.name
        ignore_index_html = True

    marimo_file = MarimoPath(name)

    def export_callback(file_path: MarimoPath) -> ExportResult:
        return export_as_wasm(file_path, mode, show_code=show_code)

    # Export assets first
    Exporter().export_assets(out_dir, ignore_index_html=ignore_index_html)

    # Create .nojekyll file to prevent GitHub Pages from interfering with asset
    # resolution
    (Path(out_dir) / ".nojekyll").touch()

    echo(
        f"Assets copied to {green(str(out_dir))}. These assets are required for the "
        "notebook to run in the browser."
    )

    did_export_public = Exporter().export_public_folder(out_dir, marimo_file)
    if did_export_public:
        echo(
            f"The public folder next to your notebook was copied to "
            f"{green(str(out_dir))}."
        )

    echo(
        "To run the exported notebook, use:\n"
        f"  python -m http.server --directory {out_dir}\n"
        "Then open the URL that is printed to your terminal."
    )

    if include_cloudflare:
        create_cloudflare_files(parse_title(name), out_dir)

    outfile = out_dir / filename
    return watch_and_export(
        MarimoPath(name), outfile, watch, export_callback, force
    )


export.add_command(html)
export.add_command(script)
export.add_command(md)
export.add_command(ipynb)
export.add_command(pdf)
export.add_command(html_wasm)
export.add_command(thumbnail)
