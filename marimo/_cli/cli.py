# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import click
from click.core import ParameterSource

import marimo._cli.cli_validators as validators
from marimo import _loggers
from marimo._ast import codegen
from marimo._cli.config.commands import config
from marimo._cli.convert.commands import convert
from marimo._cli.development.commands import development
from marimo._cli.envinfo import get_system_info
from marimo._cli.export.commands import export
from marimo._cli.files.file_path import validate_name
from marimo._cli.help_formatter import ColoredGroup
from marimo._cli.parse_args import parse_args
from marimo._cli.print import bright_green, light_blue, red
from marimo._cli.run_docker import (
    prompt_run_in_docker_container,
)
from marimo._cli.upgrade import check_for_updates, print_latest_version
from marimo._cli.utils import (
    check_app_correctness,
    check_app_correctness_or_convert,
    resolve_token,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._lint import run_check
from marimo._server.file_router import AppFileRouter, flatten_files
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.models.home import MarimoFile
from marimo._server.start import start
from marimo._session.model import SessionMode
from marimo._tutorials import (
    Tutorial,
    create_temp_tutorial_file,
    tutorial_order,
)  # type: ignore
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath, create_temp_notebook_file
from marimo._utils.platform import is_windows
from marimo._version import __version__


def helpful_usage_error(self: Any, file: Any = None) -> None:
    if file is None:
        file = click.get_text_stream("stderr")
    color = None
    click.echo(
        red("Error") + f": {self.format_message()}\n",
        file=file,
        color=color,
    )
    if self.ctx is not None:
        color = self.ctx.color
        click.echo(self.ctx.get_help(), file=file, color=color)


click.exceptions.UsageError.show = helpful_usage_error  # type: ignore


def _key_value_bullets(items: list[tuple[str, str]]) -> str:
    max_length = max(len(item[0]) for item in items)
    lines: list[str] = []

    def _sep(desc: str) -> str:
        return " " if desc else ""

    for key, desc in items:
        # "\b" tells click not to reformat our text
        lines.append("\b")
        lines.append(
            "  * "
            + light_blue(key, bold=True)
            + _sep(desc)
            + " " * (max_length - len(key) + 2)
            + desc
        )
    return "\n".join(lines)


main_help_msg = "\n".join(
    [
        "\b",
        "Welcome to marimo!",
        "\b",
        bright_green("Getting started:", bold=True),
        "",
        _key_value_bullets(
            [
                ("marimo tutorial intro", ""),
            ]
        ),
        "\b",
        "",
        bright_green("Example usage:", bold=True),
        "",
        _key_value_bullets(
            [
                (
                    "marimo edit",
                    "create or edit notebooks",
                ),
                (
                    "marimo edit notebook.py",
                    "create or edit a notebook called notebook.py",
                ),
                (
                    "marimo run notebook.py",
                    "run a notebook as a read-only app",
                ),
                (
                    "marimo tutorial --help",
                    "list tutorials",
                ),
            ]
        ),
    ]
)

token_message = (
    "Use a token for authentication. "
    "This enables session-based authentication. "
    "A random token will be generated if --token-password is not set. "
    "If --no-token is set, session-based authentication will not be used. "
)

token_password_message = (
    "Use a specific token for authentication. "
    "This enables session-based authentication. "
    "A random token will be generated if not set. "
)

sandbox_message = (
    "Run the notebook in an isolated environment, with dependencies tracked "
    "via PEP 723 inline metadata. If already declared, dependencies will "
    "install automatically. Requires uv."
)

check_message = "Disable a static check of the notebook before running."

try:
    MAX_TERM_WIDTH = shutil.get_terminal_size().columns
except Exception:
    MAX_TERM_WIDTH = 80


@click.group(
    cls=ColoredGroup,
    help=main_help_msg,
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": MAX_TERM_WIDTH,
        "show_default": True,
    },
)
@click.version_option(version=__version__, message="%(version)s")
@click.option(
    "-l",
    "--log-level",
    default="WARN",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    help="Choose logging level.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress standard out.",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Automatic yes to prompts, running non-interactively.",
)
@click.option(
    "-d",
    "--development-mode",
    is_flag=True,
    default=False,
    help="Run in development mode; enables debug logs and server autoreload.",
)
def main(
    log_level: str, quiet: bool, yes: bool, development_mode: bool
) -> None:
    log_level = "DEBUG" if development_mode else log_level
    _loggers.set_level(log_level)

    GLOBAL_SETTINGS.DEVELOPMENT_MODE = development_mode
    GLOBAL_SETTINGS.QUIET = quiet
    GLOBAL_SETTINGS.YES = yes
    GLOBAL_SETTINGS.LOG_LEVEL = _loggers.log_level_string_to_int(log_level)


def _get_stdin_contents() -> str | None:
    # Utiity to get data from stdin a nonblocking way.
    #
    # Not supported on Windows.
    #
    # We support unix-style piping, e.g. cat notebook.py | marimo edit
    # Utility to support unix-style piping, e.g. cat notebook.py | marimo edit
    #
    # This check is complicated, because we need to support running
    #
    #   marimo edit
    #
    # without a filename as well. To distinguish between `marimo edit` and
    # `... | marimo edit`, we need to check if sys.stdin() has data on it in a
    # nonblocking way. This does not seem to be possible on Windows, but it
    # is possible on unix-like systems with select.
    if not is_windows():
        import select

        try:
            if (
                not sys.stdin.isatty()
                and select.select([sys.stdin], [], [], 0)[0]
                and (contents := sys.stdin.read().strip())
            ):
                return contents
        except Exception:
            ...

    return None


edit_help_msg = "\n".join(
    [
        "\b",
        "Create or edit notebooks.",
        "",
        _key_value_bullets(
            [
                (
                    "marimo edit",
                    "Start the marimo notebook server",
                ),
                ("marimo edit notebook.py", "Create or edit notebook.py"),
            ]
        ),
    ]
)


@main.command(help=edit_help_msg)
@click.option(
    "-p",
    "--port",
    default=None,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--base-url",
    default="",
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--allow-origins",
    default=None,
    multiple=True,
    help="Allowed origins for CORS. Can be repeated. Use * for all origins.",
)
@click.option(
    "--skip-update-check",
    is_flag=True,
    default=False,
    type=bool,
    help="Don't check if a new version of marimo is available for download.",
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=sandbox_message,
)
@click.option(
    "--trusted/--untrusted",
    is_flag=True,
    default=None,
    type=bool,
    help="Run notebooks hosted remotely on the host machine; if --untrusted, runs marimo in a Docker container.",
)
@click.option("--profile-dir", default=None, type=str, hidden=True)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    type=bool,
    help="Watch the file for changes and reload the code when saved in another editor.",
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    type=bool,
    help="Enable skew protection middleware to prevent version mismatch issues.",
)
@click.option(
    "--remote-url",
    default=None,
    type=str,
    hidden=True,
    help="Remote URL for runtime configuration.",
)
@click.option(
    "--convert",
    is_flag=True,
    default=False,
    type=bool,
    hidden=True,
    help="When opening a .py file, enable fallback conversion from pypercent, script, or text.",
)
@click.option(
    "--mcp",
    is_flag=True,
    default=False,
    type=bool,
    hidden=True,
    help="Enable MCP server endpoint at /mcp/server for LLM integration.",
)
@click.option(
    "--server-startup-command",
    default=None,
    type=str,
    hidden=True,
    help="Command to run on server startup.",
)
@click.option(
    "--asset-url",
    default=None,
    type=str,
    hidden=True,
    help="Custom asset URL for loading static resources. Can include {version} placeholder.",
)
@click.option(
    "--timeout",
    required=False,
    default=None,
    type=float,
    help="Enable a global timeout to shut down the server after specified number of minutes of no connection",
)
@click.option(
    "--session-ttl",
    default=None,
    type=int,
    help="Seconds to wait before closing a session on websocket disconnect. If None is provided, sessions are not automatically closed.",
)
@click.argument(
    "name",
    required=False,
    type=click.Path(),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def edit(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    token_password_file: Optional[str],
    base_url: str,
    allow_origins: Optional[tuple[str, ...]],
    skip_update_check: bool,
    sandbox: Optional[bool],
    trusted: Optional[bool],
    profile_dir: Optional[str],
    watch: bool,
    skew_protection: bool,
    remote_url: Optional[str],
    convert: bool,
    mcp: bool,
    server_startup_command: Optional[str],
    asset_url: Optional[str],
    timeout: Optional[float],
    session_ttl: Optional[int],
    name: Optional[str],
    args: tuple[str, ...],
) -> None:
    from marimo._cli.sandbox import SandboxMode, resolve_sandbox_mode

    pass_on_stdin = token_password_file == "-"
    # We support unix-style piping, e.g. cat notebook.py | marimo edit
    if (
        not pass_on_stdin
        and name is None
        and (stdin_contents := _get_stdin_contents()) is not None
    ):
        temp_dir = tempfile.TemporaryDirectory()
        path = create_temp_notebook_file(
            "notebook.py", "py", stdin_contents, temp_dir
        )
        name = path.absolute_name

    if prompt_run_in_docker_container(name, trusted=trusted):
        from marimo._cli.run_docker import run_in_docker

        run_in_docker(
            name,
            "edit",
            port=port,
            debug=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        )
        return

    GLOBAL_SETTINGS.PROFILE_DIR = profile_dir
    if not skip_update_check and os.getenv("MARIMO_SKIP_UPDATE_CHECK") != "1":
        GLOBAL_SETTINGS.CHECK_STATUS_UPDATE = True
        # Check for version updates
        check_for_updates(print_latest_version)

    if name is not None:
        # Validate name, or download from URL
        # The second return value is an optional temporary directory. It is
        # unused, but must be kept around because its lifetime on disk is bound
        # to the life of the Python object
        name, _ = validate_name(
            name, allow_new_file=True, allow_directory=True
        )
        is_dir = os.path.isdir(name)
        if os.path.exists(name) and not is_dir:
            # module correctness check - don't start the server
            # if we can't import the module
            if convert:
                check_app_correctness_or_convert(name)
            else:
                check_app_correctness(name)
        elif not is_dir:
            # write empty file
            try:
                with open(name, "w", encoding="utf-8"):
                    pass
            except OSError as e:
                if isinstance(e, FileNotFoundError):
                    # This means that the parent directory does not exist
                    parent_dir = os.path.dirname(name)
                    raise click.ClickException(
                        f"Parent directory does not exist: {parent_dir}"
                    ) from e
                raise
    else:
        name = os.getcwd()

    # We check this after name validation, because this will convert
    # URLs into local file paths

    # Resolve sandbox mode: None, SandboxMode.SINGLE, or SandboxMode.MULTI
    sandbox_mode = resolve_sandbox_mode(sandbox=sandbox, name=name)

    # Single-file sandbox: wrap with uv run
    if sandbox_mode is SandboxMode.SINGLE:
        from marimo._cli.sandbox import run_in_sandbox

        run_in_sandbox(sys.argv[1:], name=name, additional_features=["lsp"])
        return

    # Multi-file sandbox: use IPC kernels with per-notebook sandboxed venvs
    if sandbox_mode is SandboxMode.MULTI:
        # Check for pyzmq dependency
        from marimo._dependencies.dependencies import DependencyManager

        if not DependencyManager.zmq.has():
            raise click.ClickException(
                "pyzmq is required when running the marimo edit server on a directory with --sandbox.\n"
                "Install it with: pip install 'marimo[sandbox]'\n"
                "Or: pip install pyzmq"
            )

        # Enable script metadata management for sandboxed notebooks
        os.environ["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"
        GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA = True

    # Check shared memory availability early (required for edit mode to
    # communicate between the server process and kernel subprocess)
    from marimo._utils.platform import check_shared_memory_available

    shm_available, shm_error = check_shared_memory_available()
    if not shm_available:
        _loggers.marimo_logger().error(
            f"marimo failed to start: marimo edit requires shared memory support for multiprocessing.\n\n"
            f"{shm_error}\n\n"
            "Possible solutions:\n"
            "  - If running in Docker, ensure /dev/shm is mounted with sufficient size\n"
            "    (e.g., --shm-size=256m or -v /dev/shm:/dev/shm)\n"
            "  - If /dev/shm is full, clear unused shared memory segments\n"
            "  - Use 'marimo run' instead if you only need to view notebooks"
        )
        sys.exit(1)

    start(
        file_router=AppFileRouter.infer(name),
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        headless=headless,
        mode=SessionMode.EDIT,
        include_code=True,
        watch=watch,
        skew_protection=skew_protection,
        cli_args=parse_args(args),
        argv=list(args),
        auth_token=resolve_token(
            token,
            token_password=token_password,
            token_password_file=token_password_file,
        ),
        base_url=base_url,
        allow_origins=allow_origins,
        redirect_console_to_browser=True,
        ttl_seconds=session_ttl,
        remote_url=remote_url,
        mcp=mcp,
        server_startup_command=server_startup_command,
        asset_url=asset_url,
        timeout=timeout,
        sandbox_mode=sandbox_mode,
    )


new_help_msg = "\n".join(
    [
        "\b",
        "Create an empty notebook, or generate from a prompt with AI",
        "",
        _key_value_bullets(
            [
                (
                    "marimo new",
                    "Create an empty notebook",
                ),
                (
                    'marimo new "Plot an interactive 3D surface with matplotlib."',
                    "Generate a notebook from a prompt.",
                ),
                (
                    "marimo new prompt.txt",
                    "Generate a notebook from a file containing a prompt.",
                ),
            ]
        ),
        "",
        "Visit https://marimo.app/ai for more prompt examples.",
    ]
)


@main.command(help=new_help_msg)
@click.option(
    "-p",
    "--port",
    default=None,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--base-url",
    default="",
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=sandbox_message,
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    type=bool,
    help="Enable skew protection middleware to prevent version mismatch issues.",
)
@click.option(
    "--timeout",
    required=False,
    default=None,
    type=float,
    help="Enable a global timeout to shut down the server after specified number of minutes of no connection",
)
@click.argument("prompt", required=False)
def new(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    token_password_file: Optional[str],
    base_url: str,
    sandbox: Optional[bool],
    skew_protection: bool,
    timeout: Optional[float],
    prompt: Optional[str],
) -> None:
    if sandbox:
        from marimo._cli.sandbox import run_in_sandbox

        # TODO: consider adding recommended as well
        run_in_sandbox(sys.argv[1:], name=None, additional_features=["lsp"])
        return

    file_router: Optional[AppFileRouter] = None

    if prompt is None:
        # We support unix-style prompting, cat prompt.txt | marimo new
        prompt = _get_stdin_contents()

    if prompt is not None:
        import tempfile

        from marimo._ai.text_to_notebook import text_to_notebook

        try:
            _maybe_path = Path(prompt)
            if _maybe_path.is_file():
                prompt = _maybe_path.read_text(encoding="utf-8")
        except OSError:
            # is_file() fails when, for example, the "filename" (prompt) is too long
            pass

        temp_file = None
        try:
            notebook_content = text_to_notebook(prompt)
            # On Windows, NamedTemporaryFile cannot be reopened unless
            # delete=False.
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", encoding="utf-8", delete=False
            ) as temp_file:
                temp_file.write(notebook_content)
            file_router = AppFileRouter.infer(temp_file.name)

            def _cleanup() -> None:
                try:
                    os.unlink(temp_file.name)
                except Exception:  # noqa: S110
                    pass

            atexit.register(_cleanup)
        except Exception as e:
            if temp_file is not None:
                try:
                    os.unlink(temp_file.name)
                except Exception:  # noqa: S110
                    pass

            raise click.ClickException(
                f"Failed to generate notebook: {e!s}"
            ) from e

    if file_router is None:
        file_router = AppFileRouter.new_file()

    start(
        file_router=file_router,
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        headless=headless,
        mode=SessionMode.EDIT,
        include_code=True,
        watch=False,
        skew_protection=skew_protection,
        cli_args={},
        argv=[],
        auth_token=resolve_token(
            token,
            token_password=token_password,
            token_password_file=token_password_file,
        ),
        base_url=base_url,
        redirect_console_to_browser=True,
        ttl_seconds=None,
        timeout=timeout,
    )


@dataclass(frozen=True)
class _CollectedRunFiles:
    files: list[MarimoFile]
    root_dir: str | None


def _split_run_paths_and_args(
    name: str, args: tuple[str, ...]
) -> tuple[list[str], tuple[str, ...]]:
    paths = [name]
    for index, arg in enumerate(args):
        if arg == "--":
            return paths, args[index + 1 :]
        if arg.startswith("-"):
            return paths, args[index:]
        paths.append(arg)
    return paths, ()


def _resolve_root_dir(
    directories: list[str], files: list[MarimoFile]
) -> str | None:
    # Choose a "root" directory for gallery links when there is an obvious
    # shared base directory. This lets us use relative `?file=` keys (and
    # avoids leaking absolute paths) when possible.
    if len(directories) == 1:
        directory = Path(directories[0]).absolute()
        if not files:
            return str(directory)
        # Only use this directory root if it contains all selected files.
        if all(
            Path(file.path).absolute().is_relative_to(directory)
            for file in files
        ):
            return str(directory)
        return None

    if not directories:
        if not files:
            return None
        parent = Path(files[0].path).absolute().parent
        # Only use a parent root when all files are siblings.
        if all(Path(file.path).absolute().parent == parent for file in files):
            return str(parent)

    return None


def _collect_marimo_files(paths: list[str]) -> _CollectedRunFiles:
    directories: list[str] = []
    files_by_path: dict[str, MarimoFile] = {}

    for path in paths:
        if Path(path).is_dir():
            directories.append(path)
            directory = Path(path).absolute()
            scanner = DirectoryScanner(path, include_markdown=True)
            try:
                file_infos = scanner.scan()
            except HTTPException as exc:
                if exc.status_code != HTTPStatus.REQUEST_TIMEOUT:
                    raise
                file_infos = scanner.partial_results
            for file_info in flatten_files(file_infos):
                if not file_info.is_marimo_file:
                    continue
                absolute_path = str(directory / file_info.path)
                files_by_path[absolute_path] = MarimoFile(
                    name=file_info.name,
                    path=absolute_path,
                    last_modified=file_info.last_modified,
                )
        else:
            marimo_path = MarimoPath(path)
            files_by_path[marimo_path.absolute_name] = MarimoFile(
                name=marimo_path.relative_name,
                path=marimo_path.absolute_name,
                last_modified=marimo_path.last_modified,
            )

    files = sorted(files_by_path.values(), key=lambda file: file.path)
    root_dir = _resolve_root_dir(directories, files)
    return _CollectedRunFiles(files=files, root_dir=root_dir)


@main.command(
    help="""Run a notebook as an app in read-only mode.

If NAME is a url, the notebook will be downloaded to a temporary file.

Example:

    marimo run notebook.py
    marimo run folder another_folder
    marimo run app.py -- --arg value
"""
)
@click.option(
    "-p",
    "--port",
    default=None,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=False,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--include-code",
    is_flag=True,
    default=False,
    type=bool,
    help="Include notebook code in the app.",
)
@click.option(
    "--session-ttl",
    default=120,
    type=int,
    help=("Seconds to wait before closing a session on websocket disconnect."),
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    type=bool,
    help=(
        "Watch the file for changes and reload the app. "
        "If watchdog is installed, it will be used to watch the file. "
        "Otherwise, file watcher will poll the file every 1s."
    ),
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    type=bool,
    help="Enable skew protection middleware to prevent version mismatch issues.",
)
@click.option(
    "--base-url",
    default="",
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--allow-origins",
    default=None,
    multiple=True,
    help="Allowed origins for CORS. Can be repeated.",
)
@click.option(
    "--redirect-console-to-browser",
    is_flag=True,
    default=False,
    type=bool,
    help="Redirect console logs to the browser console.",
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=sandbox_message,
)
@click.option(
    "--check/--no-check",
    is_flag=True,
    default=True,
    type=bool,
    help=check_message,
)
@click.option(
    "--trusted/--untrusted",
    is_flag=True,
    default=None,
    type=bool,
    help="Run notebooks hosted remotely on the host machine; if --untrusted, runs marimo in a Docker container.",
)
@click.option(
    "--server-startup-command",
    default=None,
    type=str,
    hidden=True,
    help="Command to run on server startup.",
)
@click.option(
    "--asset-url",
    default=None,
    type=str,
    hidden=True,
    help="Custom asset URL for loading static resources. Can include {version} placeholder.",
)
@click.pass_context
@click.argument(
    "name",
    required=True,
    type=click.Path(),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def run(
    ctx: click.Context,
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    token_password_file: Optional[str],
    include_code: bool,
    session_ttl: int,
    watch: bool,
    skew_protection: bool,
    base_url: str,
    allow_origins: tuple[str, ...],
    redirect_console_to_browser: bool,
    sandbox: Optional[bool],
    check: bool,
    trusted: Optional[bool],
    server_startup_command: Optional[str],
    asset_url: Optional[str],
    name: str,
    args: tuple[str, ...],
) -> None:
    from marimo._cli.sandbox import (
        SandboxMode,
        resolve_sandbox_mode,
        run_in_sandbox,
    )

    paths, notebook_args = _split_run_paths_and_args(name, args)

    if len(paths) == 1 and prompt_run_in_docker_container(
        paths[0], trusted=trusted
    ):
        from marimo._cli.run_docker import run_in_docker

        run_in_docker(
            paths[0],
            "run",
            port=port,
            debug=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        )
        return

    # Validate name, or download from URL
    # The second return value is an optional temporary directory. It is unused,
    # but must be kept around because its lifetime on disk is bound to the life
    # of the Python object
    validated_paths: list[str] = []
    temp_dirs: list[tempfile.TemporaryDirectory[str]] = []
    for path in paths:
        validated_path, temp_dir = validate_name(
            path, allow_new_file=False, allow_directory=True
        )
        if temp_dir is not None:
            temp_dirs.append(temp_dir)
        validated_paths.append(validated_path)

    has_directory = any(Path(path).is_dir() for path in validated_paths)
    is_multi = has_directory or len(validated_paths) > 1

    check_source = ctx.get_parameter_source("check")
    check_explicit = check_source not in (
        ParameterSource.DEFAULT,
        ParameterSource.DEFAULT_MAP,
    )

    if is_multi and check and check_explicit:
        raise click.UsageError(
            "--check is only supported when running a single notebook file."
        )

    # correctness check - don't start the server if we can't import the module
    for path in validated_paths:
        if Path(path).is_file():
            check_app_correctness(path)
            if check and not has_directory:
                from marimo._lint import collect_messages

                file = MarimoPath(path)
                linter, message = collect_messages(file.absolute_name)
                if linter.errored:
                    raise click.ClickException(
                        red("Failure")
                        + ": The notebook has errors, fix them before running.\n"
                        + message.strip()
                    )

    # We check this after name validation, because this will convert
    # URLs into local file paths
    if is_multi:
        # Gallery mode: use MULTI sandbox (IPC kernels) or None
        sandbox_mode = SandboxMode.MULTI if sandbox else None
    else:
        sandbox_mode = resolve_sandbox_mode(
            sandbox=sandbox, name=validated_paths[0]
        )
        if sandbox_mode is SandboxMode.SINGLE:
            run_in_sandbox(sys.argv[1:], name=validated_paths[0])
            return

    # Multi-file sandbox: use IPC kernels with per-notebook sandboxed venvs
    if sandbox_mode is SandboxMode.MULTI:
        # Check for pyzmq dependency
        from marimo._dependencies.dependencies import DependencyManager

        if not DependencyManager.zmq.has():
            raise click.ClickException(
                "pyzmq is required when running a gallery with --sandbox.\n"
                "Install it with: pip install 'marimo[sandbox]'\n"
                "Or: pip install pyzmq"
            )

    if is_multi:
        marimo_files = _collect_marimo_files(validated_paths)
        file_router = AppFileRouter.from_files(
            marimo_files.files,
            directory=marimo_files.root_dir,
            allow_single_file_key=False,
            allow_dynamic=False,
        )
    else:
        file_router = AppFileRouter.from_filename(
            MarimoPath(validated_paths[0])
        )

    start(
        file_router=file_router,
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        headless=headless,
        mode=SessionMode.RUN,
        include_code=include_code,
        ttl_seconds=session_ttl,
        watch=watch,
        skew_protection=skew_protection,
        base_url=base_url,
        allow_origins=allow_origins,
        cli_args=parse_args(notebook_args),
        argv=list(notebook_args),
        auth_token=resolve_token(
            token,
            token_password=token_password,
            token_password_file=token_password_file,
        ),
        redirect_console_to_browser=redirect_console_to_browser,
        server_startup_command=server_startup_command,
        asset_url=asset_url,
        sandbox_mode=sandbox_mode,
    )


@main.command(help="Recover a marimo notebook from JSON.")
@click.argument(
    "name",
    required=True,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, path_type=Path
    ),
)
def recover(name: Path) -> None:
    click.echo(codegen.recover(name))


@main.command(
    help="""Open a tutorial.

marimo is a powerful library for making reactive notebooks
and apps. To get the most out of marimo, get started with a few
tutorials, starting with the intro:

    \b
    marimo tutorial intro

Recommended sequence:

    \b
"""
    + "\n".join(f"    - {name}" for name in tutorial_order)
)
@click.option(
    "-p",
    "--port",
    default=None,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    type=str,
    help="Host to attach to.",
)
@click.option(
    "--proxy",
    default=None,
    type=str,
    help="Address of reverse proxy.",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    type=bool,
    help="Enable skew protection middleware to prevent version mismatch issues.",
)
@click.argument(
    "name",
    required=True,
    type=click.Choice(tutorial_order),
)
def tutorial(
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    headless: bool,
    token: bool,
    token_password: Optional[str],
    token_password_file: Optional[str],
    skew_protection: bool,
    name: Tutorial,
) -> None:
    temp_dir = tempfile.TemporaryDirectory()
    path = create_temp_tutorial_file(name, temp_dir)

    start(
        file_router=AppFileRouter.from_filename(path),
        development_mode=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        quiet=GLOBAL_SETTINGS.QUIET,
        host=host,
        port=port,
        proxy=proxy,
        mode=SessionMode.EDIT,
        include_code=True,
        headless=headless,
        watch=False,
        skew_protection=skew_protection,
        cli_args={},
        argv=[],
        auth_token=resolve_token(
            token,
            token_password=token_password,
            token_password_file=token_password_file,
        ),
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )


@main.command()
def env() -> None:
    """Print out environment information for debugging purposes."""
    click.echo(json.dumps(get_system_info(), indent=2))


@main.command(
    help="Install shell completions for marimo. Supports bash, zsh, and fish."
)
def shell_completion() -> None:
    shell = os.environ.get("SHELL", "")
    if not shell:
        raise click.UsageError(
            "Could not determine shell. Please set $SHELL environment variable.",
        )

    # in case we're on a windows system, use .stem to remove extension
    shell_name = Path(shell).stem

    # N.B. change the help message above when changing supported shells
    commands = {
        "bash": (
            'eval "$(_MARIMO_COMPLETE=bash_source marimo)"',
            ".bashrc",
        ),
        "zsh": (
            'eval "$(_MARIMO_COMPLETE=zsh_source marimo)"',
            ".zshrc",
        ),
        "fish": (
            "_MARIMO_COMPLETE=fish_source marimo | source",
            ".config/fish/completions/marimo.fish",
        ),
    }

    if shell_name not in commands:
        supported = ", ".join(commands.keys())
        raise click.UsageError(
            f"Unsupported shell: {shell_name} (from $SHELL). Supported shells: {supported}",
        )
        return

    cmd, rc_file = commands[shell_name]
    click.secho("Run this command to enable completions:", fg="green")
    click.secho(f"\n    echo '{cmd}' >> ~/{rc_file}\n", fg="yellow")
    click.secho(
        "\nThen restart your shell or run 'source ~/"
        + rc_file
        + "' to enable completions",
        fg="green",
    )


@main.command(help="""Check and format marimo files.""")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    type=bool,
    help="Whether to in place update files.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    type=bool,
    help="Whether warnings return a non-zero exit code.",
)
@click.option(
    "-v/-q",
    "--verbose/--quiet",
    is_flag=True,
    default=True,
    type=bool,
    help="Whether to print detailed messages.",
)
@click.option(
    "--unsafe-fixes",
    is_flag=True,
    default=False,
    type=bool,
    help="Enable fixes that may change code behavior (e.g., removing empty cells).",
)
@click.option(
    "--ignore-scripts",
    is_flag=True,
    default=False,
    type=bool,
    help="Ignore files that are not recognizable as marimo notebooks.",
)
@click.option(
    "--format",
    "formatter",
    default="full",
    type=click.Choice(["full", "json"], case_sensitive=False),
    help="Output format for diagnostics.",
)
@click.argument("files", nargs=-1, type=click.UNPROCESSED)
def check(
    fix: bool,
    strict: bool,
    verbose: bool,
    unsafe_fixes: bool,
    ignore_scripts: bool,
    formatter: str,
    files: tuple[str, ...],
) -> None:
    if not files:
        # If no files are provided, we lint the current directory
        files = ("**/*.py", "**/*.md", "**/*.qmd")

    # Pass click.echo directly as pipe for streaming output, or None for JSON
    pipe = click.echo if verbose and formatter != "json" else None
    linter = run_check(
        files,
        pipe=pipe,
        fix=fix,
        unsafe_fixes=unsafe_fixes,
        ignore_scripts=ignore_scripts,
        formatter=formatter,
    )

    if formatter == "json":
        # JSON output - let linter handle the collection and formatting
        result = linter.get_json_result()
        # Always output to stdout for JSON, regardless of errors
        click.echo(json.dumps(result), err=False)
    else:
        # Get counts from linter (fix happens automatically during streaming)
        fixed = linter.fixed_count
        total_issues = linter.issues_count

        # Final summary
        if fixed > 0:
            click.echo(f"Updated {fixed} file{'s' if fixed > 1 else ''}.")
        if total_issues > 0:
            click.echo(
                f"Found {total_issues} issue{'s' if total_issues > 1 else ''}."
            )

    if linter.errored or (strict and (fixed > 0 or total_issues > 0)):
        sys.exit(1)


main.command()(convert)
main.add_command(export)
main.add_command(config)
main.add_command(development)
