# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._cli.export._common import (
    collect_notebooks,
    run_python_subprocess,
)
from marimo._cli.export.output import STDERR
from marimo._cli.help_formatter import SandboxCommand
from marimo._cli.install_hints import get_playwright_chromium_setup_commands
from marimo._cli.parse_args import parse_args
from marimo._cli.print import echo, green, red, yellow
from marimo._cli.sandbox import (
    _strip_sandbox_args,
    _wait_on_plan,
    require_sandbox_backend,
    resolve_sandbox,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._environments.backends import launch_isolated
from marimo._environments.overlay import runtime_overlay
from marimo._export._html_asset_server import HtmlAssetServer
from marimo._export.file import export_html
from marimo._export.requests import (
    HTMLFileExportRequest,
    NotebookExecutionOptions,
)
from marimo._schemas.export_options import HTMLExportOptions
from marimo._server.utils import asyncio_run
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import marimo_package_path, maybe_make_dirs

if TYPE_CHECKING:
    from marimo._environments.sandbox import Backend


_sandbox_message = (
    "Render notebooks in an isolated environment, with dependencies tracked "
    "via PEP 723 inline metadata. If already declared, dependencies will "
    "install automatically. Use --sandbox (uv), --sandbox=uv, or "
    "--sandbox=pixi. Only applies when --execute is used."
)
_READINESS_WAIT_TIMEOUT_MS = 30_000
_sandbox_bootstrapped_env = "MARIMO_THUMBNAIL_SANDBOX_BOOTSTRAPPED"


async def _render_html(
    marimo_path: MarimoPath,
    *,
    execute: bool,
    include_code: bool,
    args: tuple[str, ...],
    asset_url: str | None = None,
    sandbox: Backend | None = None,
) -> str:
    if not execute:
        result = await export_html(
            HTMLFileExportRequest(
                path=marimo_path,
                options=HTMLExportOptions(
                    files=(),
                    include_code=True,
                    asset_url=asset_url,
                ),
            )
        )
        return result.text

    if not sandbox:
        cli_args = parse_args(args) if args else {}
        result = await export_html(
            HTMLFileExportRequest(
                path=marimo_path,
                options=HTMLExportOptions(
                    files=(),
                    include_code=include_code,
                    asset_url=asset_url,
                ),
                execution=NotebookExecutionOptions(
                    cli_args=cli_args,
                    argv=list(args),
                    stderr=STDERR,
                ),
            )
        )
        return result.text

    payload = {
        "path": marimo_path.absolute_name,
        "include_code": include_code,
        "args": list(args),
        "asset_url": asset_url,
    }

    # Render in a separate process so we can use a sandboxed venv without polluting the current environment.
    return await _render_html_in_subprocess(payload, sandbox)


async def _render_html_in_subprocess(
    payload: dict[str, Any], backend: Backend
) -> str:
    """Render a notebook to HTML in a separate Python process."""
    script = r"""
import asyncio
import json
import sys

from marimo._cli.parse_args import parse_args
from marimo._export.file import export_html
from marimo._export.requests import (
    HTMLFileExportRequest,
    NotebookExecutionOptions,
)
from marimo._schemas.export_options import HTMLExportOptions
from marimo._utils.marimo_path import MarimoPath

payload = json.loads(sys.argv[1])
path = MarimoPath(payload["path"])
include_code = bool(payload.get("include_code", False))
args = payload.get("args") or []
asset_url = payload.get("asset_url")

cli_args = parse_args(tuple(args)) if args else {}
result = asyncio.run(
    export_html(
        HTMLFileExportRequest(
            path=path,
            options=HTMLExportOptions(
                files=(),
                include_code=include_code,
                asset_url=asset_url,
            ),
            execution=NotebookExecutionOptions(
                cli_args=cli_args,
                argv=list(args),
            ),
        )
    )
)
sys.stdout.write(result.text)
"""

    return await run_python_subprocess(
        notebook_path=payload["path"],
        backend=backend,
        script=script,
        payload=payload,
        action="render notebook",
    )


async def _generate_thumbnails(
    *,
    notebooks: list[MarimoPath],
    width: int,
    height: int,
    scale: int,
    timeout_ms: int,
    output: Path | None,
    overwrite: bool,
    include_code: bool,
    execute: bool,
    notebook_args: tuple[str, ...],
    continue_on_error: bool,
    sandbox: Backend | None,
) -> None:
    from marimo._metadata.opengraph import default_opengraph_image_abs

    failures: list[tuple[MarimoPath, Exception]] = []

    try:
        from playwright.async_api import (  # type: ignore[import-not-found]
            TimeoutError as PlaywrightTimeoutError,
            async_playwright,
        )
    except ModuleNotFoundError as e:
        if getattr(e, "name", None) == "playwright":
            raise MarimoCLIMissingDependencyError(
                "Playwright is required to generate thumbnails.",
                "nbconvert[webpdf]",
                followup_commands=get_playwright_chromium_setup_commands(),
            ) from None
        raise

    static_dir = marimo_package_path() / "_static"

    with HtmlAssetServer(
        directory=static_dir, route="/__marimo_thumbnail__.html"
    ) as server:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
            )
            page = await context.new_page()
            await page.emulate_media(reduced_motion="reduce")

            for index, notebook in enumerate(notebooks):
                try:
                    out_path = (
                        output
                        if output is not None
                        else default_opengraph_image_abs(str(notebook.path))
                    )
                    if out_path.exists() and not overwrite:
                        echo(
                            red("skip")
                            + f": {notebook.short_name} (exists, use --overwrite)"
                        )
                        continue

                    maybe_make_dirs(out_path)

                    echo(f"Rendering {notebook.short_name}...")
                    html = await _render_html(
                        notebook,
                        execute=execute,
                        include_code=include_code,
                        args=notebook_args,
                        asset_url=server.base_url,
                        sandbox=sandbox,
                    )
                    server.set_html(html)

                    echo(f"Screenshotting -> {out_path}...")
                    page_url = f"{server.page_url}?v={index}"
                    await page.goto(page_url, wait_until="load")
                    # Hide chrome and watermarks marked for print so thumbnails stay focused on notebook content.
                    await page.add_style_tag(
                        content=(
                            '.print\\:hidden,[data-testid="watermark"]{display:none !important;}'
                        )
                    )
                    # Nb renderer starts cell contents as invisible for a short period to avoid flicker
                    # --> we wait for the first cell container to be visible before snapshotting.
                    try:
                        await page.wait_for_function(
                            r"""
() => {
  const root = document.getElementById("root");
  if (!root) return false;

  const cells = Array.from(document.querySelectorAll('div[id^="cell-"]'));
  if (cells.length > 0) {
    const hasVisibleCell = cells.some((cell) => {
      const style = window.getComputedStyle(cell);
      return style.visibility !== "hidden" && style.display !== "none";
    });
    if (hasVisibleCell) return true;
  }

  return root.childElementCount > 0;
}
""",
                            timeout=_READINESS_WAIT_TIMEOUT_MS,
                        )
                    except PlaywrightTimeoutError:
                        echo(
                            yellow("warning")
                            + ": readiness check timed out; capturing screenshot anyway."
                        )
                    await page.wait_for_timeout(timeout_ms)
                    await page.screenshot(path=str(out_path), full_page=False)

                    echo(green("ok") + f": {out_path}")
                except Exception as e:
                    failures.append((notebook, e))
                    echo(red("error") + f": {notebook.short_name}: {e}")
                    if not continue_on_error:
                        raise

            await context.close()
            await browser.close()

    if failures:
        raise click.ClickException(
            f"Failed to generate thumbnails for {len(failures)} notebooks."
        )


@click.command(
    "thumbnail",
    cls=SandboxCommand,
    help="Generate OpenGraph thumbnails for notebooks.",
)
@click.argument(
    "name",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=True, path_type=Path
    ),
)
@click.option(
    "--width",
    type=int,
    default=1200,
    help="Viewport width for the screenshot.",
)
@click.option(
    "--height",
    type=int,
    default=630,
    help="Viewport height for the screenshot.",
)
@click.option(
    "--scale",
    type=click.IntRange(min=1, max=4),
    default=2,
    help=(
        "Device scale factor for screenshots. Output resolution will be "
        "`width*scale` x `height*scale`."
    ),
)
@click.option(
    "--timeout-ms",
    type=int,
    default=1500,
    help="Additional time to wait after page load before screenshot.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output filename. If omitted, writes to "
        "`<notebook_dir>/__marimo__/assets/<notebook_stem>/opengraph.png`."
    ),
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Overwrite existing thumbnails.",
)
@click.option(
    "--include-code/--no-include-code",
    default=False,
    help="Whether to include code in the rendered HTML before screenshot.",
)
@click.option(
    "--execute/--no-execute",
    default=False,
    help=(
        "Execute notebooks and include their outputs in thumbnails. "
        "In --no-execute mode (default), thumbnails are generated from notebook "
        "structure without running code (and will not include outputs)."
    ),
)
@click.option(
    "--sandbox",
    default=None,
    type=click.Choice(["uv", "pixi"]),
    help=_sandbox_message,
)
@click.option(
    "--no-sandbox",
    is_flag=True,
    default=False,
    help="Never run in a sandbox, and never prompt to.",
)
@click.option(
    "--continue-on-error/--fail-fast",
    default=True,
    help="Continue processing other notebooks if one notebook fails.",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def thumbnail(
    name: Path,
    width: int,
    height: int,
    scale: int,
    timeout_ms: int,
    output: Path | None,
    overwrite: bool,
    include_code: bool,
    execute: bool,
    sandbox: str | None,
    no_sandbox: bool,
    continue_on_error: bool,
    args: tuple[str, ...],
) -> None:
    """Generate thumbnails for one or more notebooks (or directories)."""
    notebook_args: tuple[str, ...] = click.get_current_context().meta.get(
        "marimo_run_args_after_separator", ()
    )
    targets = args[: -len(notebook_args)] if notebook_args else args
    paths = [str(name), *targets]
    path_targets = [Path(p) for p in paths]
    notebooks = collect_notebooks(path_targets)
    if not notebooks:
        raise click.ClickException("No marimo notebooks found.")
    if output is not None and len(notebooks) > 1:
        raise click.UsageError(
            "--output can only be used when generating thumbnail for a single notebook."
        )

    if not execute and sandbox and not no_sandbox:
        raise click.UsageError("--sandbox requires --execute.")

    bootstrapped = os.environ.get(_sandbox_bootstrapped_env)
    backend = (
        resolve_sandbox(
            sandbox or bootstrapped,
            no_sandbox,
            str(name) if len(path_targets) == 1 else None,
        )
        if execute
        else None
    )

    if backend and not bootstrapped:
        require_sandbox_backend(backend)
        # The renderer needs Playwright, not a notebook-bound environment
        # whose identity would be inherited by the export workers.
        sys.exit(
            _wait_on_plan(
                launch_isolated(
                    ["-m", "marimo", *_strip_sandbox_args(sys.argv[1:])],
                    requirements=runtime_overlay(
                        command=["playwright"]
                    ).requirements,
                    python=sys.executable,
                    backend=backend,
                    base_env={
                        **os.environ,
                        _sandbox_bootstrapped_env: backend,
                    },
                )
            )
        )

    try:
        DependencyManager.playwright.require("for thumbnail generation")
    except ModuleNotFoundError as e:
        if getattr(e, "name", None) == "playwright":
            raise MarimoCLIMissingDependencyError(
                "Playwright is required for thumbnail generation.",
                "playwright",
                followup_commands=get_playwright_chromium_setup_commands(),
            ) from None
        raise

    asyncio_run(
        _generate_thumbnails(
            notebooks=notebooks,
            width=width,
            height=height,
            scale=scale,
            timeout_ms=timeout_ms,
            output=output,
            overwrite=overwrite,
            include_code=include_code,
            execute=execute,
            notebook_args=notebook_args,
            continue_on_error=continue_on_error,
            sandbox=backend,
        )
    )
