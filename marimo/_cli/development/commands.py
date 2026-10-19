# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from marimo._cli.errors import (
    MarimoCLIMissingDependencyError,
    MarimoCLIRuntimeError,
)
from marimo._cli.help_formatter import ColoredCommand, ColoredGroup

if TYPE_CHECKING:
    import psutil


@click.group(
    cls=ColoredGroup,
    help="""Various commands for the marimo development.""",
    hidden=True,
)
def development() -> None:
    pass


@click.command(cls=ColoredCommand, help="""Print the marimo OpenAPI schema""")
def openapi() -> None:
    """
    Example usage:

        marimo development openapi
    """
    import yaml

    from marimo._cli.development.schema import generate_server_api_schema

    click.echo(
        yaml.dump(generate_server_api_schema(), default_flow_style=False)
    )


@click.group(
    cls=ColoredGroup,
    help="Various commands for the marimo processes",
    hidden=True,
)
def ps() -> None:
    pass


def get_marimo_processes() -> list[psutil.Process]:
    import psutil

    def is_marimo_process(proc: psutil.Process) -> bool:
        if proc.name() == "marimo":
            return True

        if proc.name().lower() == "python":
            try:
                cmds = proc.cmdline()
            except psutil.AccessDenied:
                return False
            except psutil.ZombieProcess:
                return False
            # any endswith marimo
            has_marimo = any(x.endswith("marimo") for x in cmds)
            # any command equals "tutorial", "edit", or "run"
            has_running_command = any(
                x in {"run", "tutorial", "edit"} for x in cmds
            )
            return has_marimo and has_running_command

        return False

    result: list[psutil.Process] = []

    for proc in psutil.process_iter():
        if is_marimo_process(proc):
            result.append(proc)

    return result


@ps.command(help="List the marimo processes", name="list")
def list_processes() -> None:
    """
    Example usage:

        marimo development ps list
    """
    from marimo._cli.print import orange

    # pretty print processes
    result = get_marimo_processes()
    for proc in result:
        cmds = proc.cmdline()
        cmd = " ".join(cmds[1:])
        click.echo(f"PID: {orange(str(proc.pid))} | {cmd}")


@ps.command(help="Kill the marimo processes")
def killall() -> None:
    """
    Example usage:

        marimo development ps killall
    """

    for proc in get_marimo_processes():
        # Ignore self
        if proc.pid == os.getpid():
            continue
        proc.kill()
        click.echo(f"Killed process {proc.pid}")

    click.echo("Killed all marimo processes")


@click.command(
    cls=ColoredCommand,
    help="Inline packages according to PEP 723",
    name="inline-packages",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(
        path_type=Path, exists=True, file_okay=True, dir_okay=False
    ),
)
def inline_packages(name: Path) -> None:
    """
    Example usage:

        marimo development inline-packages

    This uses some heuristics to guess the package names from the imports in
    the file.

    Requires uv.
    Installation: https://docs.astral.sh/uv/getting-started/installation/
    """
    from marimo._dependencies.dependencies import DependencyManager
    from marimo._runtime.packages.module_name_to_pypi_name import (
        module_name_to_pypi_name,
    )

    # Validate uv is installed
    if not DependencyManager.which("uv"):
        raise MarimoCLIMissingDependencyError(
            "uv is not installed.",
            "uv",
            additional_tip=(
                "See https://docs.astral.sh/uv/getting-started/installation/"
            ),
        )

    # Validate the file exists
    if not name.exists():
        raise click.FileError(str(name))

    package_names = module_name_to_pypi_name()

    def get_pypi_package_names() -> list[str]:
        tree = ast.parse(name.read_text(encoding="utf-8"), filename=name)

        imported_modules = set[str]()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".")[0])

        pypi_names = [
            package_names.get(mod, mod.replace("_", "-"))
            for mod in imported_modules
        ]

        return pypi_names

    def is_stdlib_module(module_name: str) -> bool:
        return module_name in sys.stdlib_module_names

    pypi_names = get_pypi_package_names()

    # Filter out python distribution packages
    pypi_names = [name for name in pypi_names if not is_stdlib_module(name)]

    click.echo(f"Inlining packages: {pypi_names}")
    click.echo(f"into script: {name}")
    subprocess.run(
        [
            "uv",
            "add",
            "--script",
            str(name),
        ]
        + pypi_names
    )


@click.command(cls=ColoredCommand, help="Print all routes")
def print_routes() -> None:
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route, Router

    from marimo._server.main import create_starlette_app

    app = create_starlette_app(base_url="")

    def print_all_routes(app: Any, base_path: str = "") -> None:
        if not isinstance(app, (Starlette, Router)):
            return
        for route in app.routes:
            if isinstance(route, Route) and route.methods is not None:
                full_path = base_path + route.path
                for method in route.methods:
                    if method == "HEAD":
                        continue
                    click.echo(f"{method} {full_path}")
            elif isinstance(route, Mount) and route.app is not None:
                # Recursively append base path for mounted apps
                new_base_path = base_path + route.path
                print_all_routes(route.app, new_base_path)

    print_all_routes(app)
    return


@click.command(cls=ColoredCommand, help="Preview a marimo file as static HTML")
@click.argument(
    "file_path",
    required=True,
    type=click.Path(
        path_type=Path, exists=True, file_okay=True, dir_okay=False
    ),
)
@click.option(
    "--port",
    default=8080,
    help="Port to serve the preview on",
    type=int,
)
@click.option(
    "--host",
    default="localhost",
    help="Host to serve the preview on",
    type=str,
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    help="Don't automatically open the browser",
)
def preview(file_path: Path, port: int, host: str, headless: bool) -> None:
    """
    Preview a marimo file as static HTML.

    Creates a static HTML export of the marimo file and serves it
    on a simple HTTP server for preview purposes.

    Example usage:
        marimo development preview my_notebook.py
        marimo development preview my_notebook.py --port 8000
    """
    import threading
    import webbrowser

    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.staticfiles import StaticFiles

    from marimo._config.config import DEFAULT_CONFIG
    from marimo._server.tokens import SkewProtectionToken
    from marimo._templates import static_notebook_template
    from marimo._utils.paths import marimo_package_path

    if TYPE_CHECKING:
        from starlette.requests import Request

    try:
        # Run the notebook to get actual outputs
        click.echo(f"Running notebook {file_path.name}...")
        from marimo._cli.export.output import STDERR
        from marimo._export.file import run_notebook
        from marimo._export.requests import (
            NotebookExecutionOptions,
            RunNotebookRequest,
        )
        from marimo._server.utils import asyncio_run
        from marimo._session.notebook import load_notebook
        from marimo._session.state.serialize import (
            serialize_notebook,
            serialize_session_view,
        )
        from marimo._utils.code import hash_code

        # Create file manager for the notebook
        file_manager = load_notebook(file_path)

        # Run the notebook to completion and get session view
        session_view, did_error = asyncio_run(
            run_notebook(
                RunNotebookRequest(
                    file_manager=file_manager,
                    options=NotebookExecutionOptions(
                        cli_args={},
                        argv=None,
                        stderr=STDERR,
                    ),
                )
            )
        )
        if did_error:
            click.echo(
                "Warning: Some cells had errors during execution", err=True
            )

        # Create session snapshot from the executed session
        session_snapshot = serialize_session_view(
            session_view,
            cell_ids=list(file_manager.app.cell_manager.cell_ids()),
            drop_virtual_file_outputs=False,
        )

        # Get notebook snapshot from file manager
        notebook_snapshot = serialize_notebook(
            session_view, file_manager.app.cell_manager
        )

        # Get the static assets directory
        static_root = marimo_package_path() / "_static"

        # Get base HTML template
        template_path = static_root / "index.html"

        html_template = template_path.read_text(encoding="utf-8")

        # Use local assets instead of CDN
        asset_url = f"http://{host}:{port}"
        code = file_path.read_text(encoding="utf-8")

        # Generate static HTML
        html_content = static_notebook_template(
            html=html_template,
            user_config=DEFAULT_CONFIG,
            config_overrides={},
            server_token=SkewProtectionToken("preview"),
            app_config=file_manager.app.config,
            filepath=str(file_path),
            code=code,
            session_snapshot=session_snapshot,
            code_hash=hash_code(code),
            notebook_snapshot=notebook_snapshot,
            files={},
            layout=file_manager.read_layout_config(),
            model_notifications=session_view.get_model_notifications(),
            asset_url=asset_url,
        )

        click.echo(f"Creating preview for {file_path.name}")

        async def serve_html(request: Request) -> HTMLResponse:
            del request
            return HTMLResponse(html_content)

        # Create Starlette app
        app = Starlette(
            routes=[
                Route("/", serve_html),
                Route("/index.html", serve_html),
            ]
        )

        # Mount static files for assets
        app.mount(
            "/assets",
            StaticFiles(directory=static_root / "assets"),
            name="assets",
        )

        # Mount other static files (favicon, icons, manifest, etc.)
        app.mount(
            "/",
            StaticFiles(directory=static_root, html=False),
            name="static",
        )

        url = f"http://{host}:{port}"
        click.echo(f"Serving preview at {url}")
        click.echo("Press Ctrl+C to stop the server")

        # Open browser if requested
        if not headless:

            def open_browser() -> None:
                webbrowser.open(url)

            timer = threading.Timer(1.0, open_browser)
            timer.start()

        # Run the server
        uvicorn.run(app, host=host, port=port, log_level="error")

    except Exception as e:
        raise MarimoCLIRuntimeError(f"Error creating preview: {e}") from e


development.add_command(inline_packages)
development.add_command(openapi)
development.add_command(ps)
development.add_command(print_routes)
development.add_command(preview)
