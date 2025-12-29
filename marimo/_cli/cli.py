# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import click

import marimo._cli.cli_validators as validators
from marimo import _loggers
from marimo._ast import codegen
from marimo._cli.config.commands import config
from marimo._cli.convert.commands import convert
from marimo._cli.development.commands import development
from marimo._cli.envinfo import get_system_info
from marimo._cli.export.commands import export
from marimo._cli.file_path import validate_name
from marimo._cli.parse_args import parse_args
from marimo._cli.print import red
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
from marimo._server.file_router import AppFileRouter
from marimo._server.start import start
from marimo._session.model import SessionMode
from marimo._tutorials import (
    Tutorial,
    create_temp_tutorial_file,
    tutorial_order,
)  # type: ignore
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
            + key
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
        "Getting started:",
        "",
        _key_value_bullets(
            [
                ("marimo tutorial intro", ""),
            ]
        ),
        "\b",
        "",
        "Example usage:",
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


@click.group(
    help=main_help_msg,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__, message="%(version)s")
@click.option(
    "-l",
    "--log-level",
    default="WARN",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    show_default=True,
    help="Choose logging level.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    default=False,
    show_default=True,
    help="Suppress standard out.",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    show_default=True,
    help="Automatic yes to prompts, running non-interactively.",
)
@click.option(
    "-d",
    "--development-mode",
    is_flag=True,
    default=False,
    show_default=True,
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
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    show_default=True,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Don't check if a new version of marimo is available for download.",
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    show_default=False,
    type=bool,
    help=sandbox_message,
)
@click.option(
    "--dangerous-sandbox/--no-dangerous-sandbox",
    is_flag=True,
    default=None,
    show_default=False,
    type=bool,
    hidden=True,
    help="""Enables the usage of package sandboxing when running a multi-edit
notebook server. This behavior can lead to surprising and unintended consequences,
such as incorrectly overwriting package requirements or failing to write out
requirements. These and other issues are described in
https://github.com/marimo-team/marimo/issues/5219.""",
)
@click.option(
    "--trusted/--untrusted",
    is_flag=True,
    default=None,
    show_default=False,
    type=bool,
    help="Run notebooks hosted remotely on the host machine; if --untrusted, runs marimo in a Docker container.",
)
@click.option("--profile-dir", default=None, type=str, hidden=True)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Watch the file for changes and reload the code when saved in another editor.",
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    show_default=True,
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
    show_default=True,
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
    show_default=False,
    type=float,
    help="Enable a global timeout to shut down the server after specified number of minutes of no connection",
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
    dangerous_sandbox: Optional[bool],
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
    name: Optional[str],
    args: tuple[str, ...],
) -> None:
    from marimo._cli.sandbox import run_in_sandbox, should_run_in_sandbox

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
    if should_run_in_sandbox(
        sandbox=sandbox, dangerous_sandbox=dangerous_sandbox, name=name
    ):
        from marimo._cli.sandbox import run_in_sandbox

        # TODO: consider adding recommended as well
        run_in_sandbox(sys.argv[1:], name=name, additional_features=["lsp"])
        return

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
        ttl_seconds=None,
        remote_url=remote_url,
        mcp=mcp,
        server_startup_command=server_startup_command,
        asset_url=asset_url,
        timeout=timeout,
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
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    show_default=True,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    show_default=False,
    type=bool,
    help=sandbox_message,
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    show_default=True,
    type=bool,
    help="Enable skew protection middleware to prevent version mismatch issues.",
)
@click.option(
    "--timeout",
    required=False,
    default=None,
    show_default=False,
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
                except Exception:
                    pass

            atexit.register(_cleanup)
        except Exception as e:
            if temp_file is not None:
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass

            raise click.ClickException(
                f"Failed to generate notebook: {str(e)}"
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


@main.command(
    help="""Run a notebook as an app in read-only mode.

If NAME is a url, the notebook will be downloaded to a temporary file.

Example:

    marimo run notebook.py
"""
)
@click.option(
    "-p",
    "--port",
    default=None,
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=False,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    show_default=True,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--include-code",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Include notebook code in the app.",
)
@click.option(
    "--session-ttl",
    default=120,
    show_default=True,
    type=int,
    help=("Seconds to wait before closing a session on websocket disconnect."),
)
@click.option(
    "--watch",
    is_flag=True,
    default=False,
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Enable skew protection middleware to prevent version mismatch issues.",
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Redirect console logs to the browser console.",
)
@click.option(
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    show_default=False,
    type=bool,
    help=sandbox_message,
)
@click.option(
    "--check/--no-check",
    is_flag=True,
    default=True,
    show_default=False,
    type=bool,
    help=check_message,
)
@click.option(
    "--trusted/--untrusted",
    is_flag=True,
    default=None,
    show_default=False,
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
@click.argument(
    "name",
    required=True,
    type=click.Path(),
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def run(
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
    from marimo._cli.sandbox import run_in_sandbox, should_run_in_sandbox

    if prompt_run_in_docker_container(name, trusted=trusted):
        from marimo._cli.run_docker import run_in_docker

        run_in_docker(
            name,
            "run",
            port=port,
            debug=GLOBAL_SETTINGS.DEVELOPMENT_MODE,
        )
        return

    # Validate name, or download from URL
    # The second return value is an optional temporary directory. It is unused,
    # but must be kept around because its lifetime on disk is bound to the life
    # of the Python object
    name, _ = validate_name(name, allow_new_file=False, allow_directory=False)

    # correctness check - don't start the server if we can't import the module
    check_app_correctness(name)
    file = MarimoPath(name)
    if check:
        from marimo._lint import collect_messages

        linter, message = collect_messages(file.absolute_name)
        if linter.errored:
            raise click.ClickException(
                red("Failure")
                + ": The notebook has errors, fix them before running.\n"
                + message.strip()
            )

    # We check this after name validation, because this will convert
    # URLs into local file paths
    if should_run_in_sandbox(
        sandbox=sandbox, dangerous_sandbox=None, name=name
    ):
        run_in_sandbox(sys.argv[1:], name=name)
        return

    start(
        file_router=AppFileRouter.from_filename(file),
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
        cli_args=parse_args(args),
        argv=list(args),
        auth_token=resolve_token(
            token,
            token_password=token_password,
            token_password_file=token_password_file,
        ),
        redirect_console_to_browser=redirect_console_to_browser,
        server_startup_command=server_startup_command,
        asset_url=asset_url,
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
    show_default=True,
    type=int,
    help="Port to attach to.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.option(
    "--token/--no-token",
    default=True,
    show_default=True,
    type=bool,
    help=token_message,
)
@click.option(
    "--token-password",
    default=None,
    show_default=True,
    type=str,
    help=token_password_message,
)
@click.option(
    "--token-password-file",
    default=None,
    show_default=True,
    type=str,
    help="Path to file containing token password, or '-' for stdin. Mutually exclusive with --token-password.",
)
@click.option(
    "--skew-protection/--no-skew-protection",
    is_flag=True,
    default=True,
    show_default=True,
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
    show_default=True,
    type=bool,
    help="Whether to in place update files.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Whether warnings return a non-zero exit code.",
)
@click.option(
    "-v/-q",
    "--verbose/--quiet",
    is_flag=True,
    default=True,
    show_default=True,
    type=bool,
    help="Whether to print detailed messages.",
)
@click.option(
    "--unsafe-fixes",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Enable fixes that may change code behavior (e.g., removing empty cells).",
)
@click.option(
    "--ignore-scripts",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Ignore files that are not recognizable as marimo notebooks.",
)
@click.option(
    "--format",
    "formatter",
    default="full",
    show_default=True,
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
