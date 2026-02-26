# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from contextlib import AbstractContextManager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import click

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._cli.install_hints import get_playwright_chromium_setup_commands
from marimo._cli.parse_args import parse_args
from marimo._cli.print import echo, green, red, yellow
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.export import run_app_then_export_as_html
from marimo._server.file_router import flatten_files
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.utils import asyncio_run
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import marimo_package_path, maybe_make_dirs

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType

    from marimo._cli.sandbox import SandboxMode


_sandbox_message = (
    "Render notebooks in an isolated environment, with dependencies tracked "
    "via PEP 723 inline metadata. If already declared, dependencies will "
    "install automatically. Requires uv. Only applies when --execute is used."
)
_READINESS_WAIT_TIMEOUT_MS = 30_000
_sandbox_bootstrapped_env = "MARIMO_THUMBNAIL_SANDBOX_BOOTSTRAPPED"
_sandbox_mode_env = "MARIMO_THUMBNAIL_SANDBOX_MODE"
_thumbnail_sandbox_deps = ["playwright"]


def _split_paths_and_args(
    name: str, args: tuple[str, ...]
) -> tuple[list[str], tuple[str, ...]]:
    paths = [name]
    for index, arg in enumerate(args):
        if arg == "--":
            return paths, args[index + 1 :]
        paths.append(arg)
    return paths, ()


def _collect_notebooks(paths: Iterable[Path]) -> list[MarimoPath]:
    notebooks: dict[str, MarimoPath] = {}

    for path in paths:
        if path.is_dir():
            scanner = DirectoryScanner(str(path), include_markdown=True)
            try:
                file_infos = scanner.scan()
            except HTTPException as e:
                if e.status_code != HTTPStatus.REQUEST_TIMEOUT:
                    raise
                # Match server behavior: use partial results on scan timeout.
                file_infos = scanner.partial_results
            for file_info in flatten_files(file_infos):
                if not file_info.is_marimo_file or file_info.is_directory:
                    continue
                absolute_path = str(Path(path) / file_info.path)
                notebooks[absolute_path] = MarimoPath(absolute_path)
        else:
            notebooks[str(path)] = MarimoPath(str(path))

    return [notebooks[k] for k in sorted(notebooks)]


def _is_multi_target(paths: list[Path]) -> bool:
    return len(paths) > 1 or any(path.is_dir() for path in paths)


def _sandbox_mode_from_env() -> SandboxMode | None:
    from marimo._cli.sandbox import SandboxMode

    if os.environ.get(_sandbox_bootstrapped_env) != "1":
        return None

    mode = os.environ.get(_sandbox_mode_env)
    if mode == SandboxMode.SINGLE.value:
        return SandboxMode.SINGLE
    if mode == SandboxMode.MULTI.value:
        return SandboxMode.MULTI
    return None


def _resolve_thumbnail_sandbox_mode(
    *,
    execute: bool,
    sandbox: bool | None,
    path_targets: list[Path],
    first_target: str,
) -> SandboxMode | None:
    from marimo._cli.sandbox import SandboxMode, resolve_sandbox_mode

    if not execute:
        return None

    env_mode = _sandbox_mode_from_env()
    if env_mode is not None:
        return env_mode

    if _is_multi_target(path_targets):
        if sandbox is None:
            return None
        return SandboxMode.MULTI if sandbox else None

    return resolve_sandbox_mode(sandbox=sandbox, name=first_target)


def _bootstrap_thumbnail_sandbox(
    *,
    args: list[str],
    name: str,
    sandbox_mode: SandboxMode,
) -> None:
    from marimo._cli.sandbox import run_in_sandbox

    run_in_sandbox(
        args,
        name=name,
        additional_deps=_thumbnail_sandbox_deps,
        extra_env={
            _sandbox_bootstrapped_env: "1",
            _sandbox_mode_env: sandbox_mode.value,
        },
    )


async def _render_html(
    marimo_path: MarimoPath,
    *,
    execute: bool,
    include_code: bool,
    args: tuple[str, ...],
    asset_url: str | None = None,
    venv_python: str | None = None,
) -> str:
    if not execute:
        from marimo._server.export import export_as_html_without_execution

        result = await export_as_html_without_execution(
            marimo_path, include_code=True, asset_url=asset_url
        )
        return result.text

    if venv_python is None:
        cli_args = parse_args(args) if args else {}
        result = await run_app_then_export_as_html(
            marimo_path,
            include_code=include_code,
            cli_args=cli_args,
            argv=list(args),
            asset_url=asset_url,
        )
        return result.text

    payload = {
        "path": marimo_path.absolute_name,
        "include_code": include_code,
        "args": list(args),
        "asset_url": asset_url,
    }

    # Render in a separate process so we can use a sandboxed venv without polluting the current environment.
    return await asyncio.to_thread(
        _render_html_in_subprocess,
        venv_python,
        payload,
    )


def _render_html_in_subprocess(
    venv_python: str, payload: dict[str, Any]
) -> str:
    """Render a notebook to HTML in a separate Python process."""
    script = r"""
import asyncio
import json
import sys

from marimo._cli.parse_args import parse_args
from marimo._server.export import run_app_then_export_as_html
from marimo._utils.marimo_path import MarimoPath

payload = json.loads(sys.argv[1])
path = MarimoPath(payload["path"])
include_code = bool(payload.get("include_code", False))
args = payload.get("args") or []
asset_url = payload.get("asset_url")

cli_args = parse_args(tuple(args)) if args else {}
result = asyncio.run(
    run_app_then_export_as_html(
        path,
        include_code=include_code,
        cli_args=cli_args,
        argv=list(args),
        asset_url=asset_url,
    )
)
sys.stdout.write(result.text)
"""

    result = subprocess.run(
        [venv_python, "-c", script, json.dumps(payload)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise click.ClickException(
            "Failed to render notebook in sandbox.\n\n"
            f"Command:\n\n  {venv_python} -c <script>\n\n"
            f"Stderr:\n\n{stderr}"
        )
    return result.stdout


class _ThumbnailRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/__marimo_thumbnail__.html":
            html = getattr(self.server, "thumbnail_html", "")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return
        return super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Silence noisy server logs for CLI usage.
        del format
        del args
        return


class _ThumbnailHTTPServer(ThreadingHTTPServer):
    # Set by _ThumbnailAssetServer to serve a fresh HTML document per notebook.
    thumbnail_html: str


class _ThumbnailAssetServer(AbstractContextManager["_ThumbnailAssetServer"]):
    def __init__(self, *, directory: Path) -> None:
        self._directory = directory
        self._server: _ThumbnailHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        if isinstance(host, bytes):
            host = host.decode("utf-8")
        return f"http://{host}:{port}"

    @property
    def page_url(self) -> str:
        return f"{self.base_url}/__marimo_thumbnail__.html"

    def set_html(self, html: str) -> None:
        assert self._server is not None
        self._server.thumbnail_html = html

    def __enter__(self) -> _ThumbnailAssetServer:
        if not self._directory.is_dir():
            raise click.ClickException(
                f"Static assets not found at {self._directory}"
            )

        handler = partial(
            _ThumbnailRequestHandler, directory=str(self._directory)
        )
        self._server = _ThumbnailHTTPServer(("127.0.0.1", 0), handler)
        self._server.thumbnail_html = ""

        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type
        del exc
        del tb
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        return None


class _SandboxVenvPool:
    def __init__(self) -> None:
        self._envs: dict[tuple[str, ...], tuple[str, str]] = {}

    def get_python(self, notebook_path: str) -> str:
        """Return a venv python path for the notebook's sandbox requirements."""
        from marimo._cli.sandbox import (
            build_sandbox_venv,
            get_sandbox_requirements,
        )

        requirements = tuple(get_sandbox_requirements(notebook_path))
        existing = self._envs.get(requirements)
        if existing is not None:
            return existing[1]

        sandbox_dir, venv_python = build_sandbox_venv(notebook_path)
        self._envs[requirements] = (sandbox_dir, venv_python)
        return venv_python

    def close(self) -> None:
        """Clean up any sandbox environments we created."""
        from marimo._cli.sandbox import cleanup_sandbox_dir

        for sandbox_dir, _ in self._envs.values():
            cleanup_sandbox_dir(sandbox_dir)
        self._envs.clear()


async def _generate_thumbnails(
    *,
    notebooks: list[MarimoPath],
    width: int,
    height: int,
    scale: int,
    timeout_ms: int,
    output: Optional[Path],
    overwrite: bool,
    include_code: bool,
    execute: bool,
    notebook_args: tuple[str, ...],
    continue_on_error: bool,
    sandbox_mode: SandboxMode | None,
) -> None:
    from marimo._cli.sandbox import SandboxMode
    from marimo._metadata.opengraph import default_opengraph_image

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

    use_per_notebook_sandbox = sandbox_mode is SandboxMode.MULTI

    if use_per_notebook_sandbox and not DependencyManager.which("uv"):
        raise MarimoCLIMissingDependencyError(
            "uv is required for --sandbox thumbnail generation.",
            "uv",
            additional_tip="Install uv from https://github.com/astral-sh/uv",
        )

    static_dir = marimo_package_path() / "_static"

    sandbox_pool: _SandboxVenvPool | None = (
        _SandboxVenvPool() if use_per_notebook_sandbox else None
    )
    try:
        with _ThumbnailAssetServer(directory=static_dir) as server:
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
                        notebook_dir = notebook.path.parent
                        out_path = (
                            output
                            if output is not None
                            else notebook_dir
                            / default_opengraph_image(str(notebook.path))
                        )
                        if out_path.exists() and not overwrite:
                            echo(
                                red("skip")
                                + f": {notebook.short_name} (exists, use --overwrite)"
                            )
                            continue

                        maybe_make_dirs(out_path)

                        echo(f"Rendering {notebook.short_name}...")
                        venv_python = (
                            sandbox_pool.get_python(str(notebook.path))
                            if sandbox_pool is not None
                            else None
                        )
                        html = await _render_html(
                            notebook,
                            execute=execute,
                            include_code=include_code,
                            args=notebook_args,
                            asset_url=server.base_url,
                            venv_python=venv_python,
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
                        await page.screenshot(
                            path=str(out_path), full_page=False
                        )

                        echo(green("ok") + f": {out_path}")
                    except Exception as e:
                        failures.append((notebook, e))
                        echo(red("error") + f": {notebook.short_name}: {e}")
                        if not continue_on_error:
                            raise

                await context.close()
                await browser.close()
    finally:
        if sandbox_pool is not None:
            sandbox_pool.close()

    if failures:
        raise click.ClickException(
            f"Failed to generate thumbnails for {len(failures)} notebooks."
        )


@click.command(
    "thumbnail", help="Generate OpenGraph thumbnails for notebooks."
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
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
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
    output: Optional[Path],
    overwrite: bool,
    include_code: bool,
    execute: bool,
    sandbox: Optional[bool],
    continue_on_error: bool,
    args: tuple[str, ...],
) -> None:
    """Generate thumbnails for one or more notebooks (or directories)."""
    paths, notebook_args = _split_paths_and_args(str(name), args)
    path_targets = [Path(p) for p in paths]
    notebooks = _collect_notebooks(path_targets)
    if not notebooks:
        raise click.ClickException("No marimo notebooks found.")
    if output is not None and len(notebooks) > 1:
        raise click.UsageError(
            "--output can only be used when generating thumbnail for a single notebook."
        )

    if not execute and sandbox:
        raise click.UsageError("--sandbox requires --execute.")

    sandbox_mode = _resolve_thumbnail_sandbox_mode(
        execute=execute,
        sandbox=sandbox,
        path_targets=path_targets,
        first_target=str(name),
    )

    if (
        execute
        and sandbox_mode is not None
        and _sandbox_mode_from_env() is None
    ):
        _bootstrap_thumbnail_sandbox(
            args=sys.argv[1:],
            name=str(name),
            sandbox_mode=sandbox_mode,
        )
        return

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
            sandbox_mode=sandbox_mode,
        )
    )
