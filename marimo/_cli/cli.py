# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import json
import os
import pathlib
import tempfile
from typing import Any, Literal, Optional

import click

import marimo._cli.cli_validators as validators
from marimo import __version__, _loggers
from marimo._ast import codegen
from marimo._cli import ipynb_to_marimo
from marimo._cli.envinfo import get_system_info
from marimo._cli.export.commands import export
from marimo._cli.file_path import validate_name
from marimo._cli.parse_args import parse_args
from marimo._cli.print import red
from marimo._cli.upgrade import check_for_updates
from marimo._server.file_router import AppFileRouter
from marimo._server.model import SessionMode
from marimo._server.start import start

DEVELOPMENT_MODE = False
QUIET = False


def helpful_usage_error(self: Any, file: Any = None) -> None:
    if file is None:
        file = click.get_text_stream("stderr")
    color = None
    click.echo(
        red("Error") + ": %s\n" % self.format_message(),
        file=file,
        color=color,
    )
    if self.ctx is not None:
        color = self.ctx.color
        click.echo(self.ctx.get_help(), file=file, color=color)


click.exceptions.UsageError.show = helpful_usage_error  # type: ignore


def _key_value_bullets(items: list[tuple[str, str]]) -> str:
    max_length = max(len(item[0]) for item in items)
    lines = []

    def _sep(desc: str) -> str:
        return ":" if desc else ""

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
        _key_value_bullets(
            [
                ("marimo tutorial intro", ""),
            ]
        ),
        "\b",
        "Example usage:",
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


@click.group(help=main_help_msg)
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
    "-d",
    "--development-mode",
    is_flag=True,
    default=False,
    show_default=True,
    help="Run in development mode; enables debug logs and server autoreload.",
)
def main(log_level: str, quiet: bool, development_mode: bool) -> None:
    log_level = "DEBUG" if development_mode else log_level
    _loggers.set_level(log_level)

    global DEVELOPMENT_MODE
    global QUIET
    DEVELOPMENT_MODE = development_mode
    QUIET = quiet


edit_help_msg = "\n".join(
    [
        "\b",
        "Create or edit notebooks.",
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
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.argument("name", required=False)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def edit(
    port: Optional[int],
    host: str,
    headless: bool,
    name: Optional[str],
    args: tuple[str],
) -> None:
    # Check for version updates
    check_for_updates()

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
            codegen.get_app(name)
        elif not is_dir:
            # write empty file
            try:
                with open(name, "w"):
                    pass
            except OSError:
                raise
    else:
        name = os.getcwd()

    start(
        file_router=AppFileRouter.infer(name),
        development_mode=DEVELOPMENT_MODE,
        quiet=QUIET,
        host=host,
        port=port,
        headless=headless,
        mode=SessionMode.EDIT,
        include_code=True,
        watch=False,
        cli_args=parse_args(args),
    )


@main.command(help="Create a new notebook.")
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
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
def new(
    port: Optional[int],
    host: str,
    headless: bool,
) -> None:
    start(
        file_router=AppFileRouter.new_file(),
        development_mode=DEVELOPMENT_MODE,
        quiet=QUIET,
        host=host,
        port=port,
        headless=headless,
        mode=SessionMode.EDIT,
        include_code=True,
        watch=False,
        cli_args={},
    )


@main.command(
    help="""Run a notebook as an app in read-only mode.

If NAME is a url, the notebook will be downloaded to a temporary file.

Example:

  \b
  * marimo run notebook.py
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
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
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
    "--watch",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="""
    Watch the file for changes and reload the app.
    If watchdog is installed, it will be used to watch the file.
    Otherwise, file watcher will poll the file every 1s.
    """,
)
@click.option(
    "--base-url",
    default="",
    show_default=True,
    type=str,
    help="Base URL for the server. Should start with a /.",
    callback=validators.base_url,
)
@click.argument("name", required=True)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def run(
    port: Optional[int],
    host: str,
    headless: bool,
    include_code: bool,
    watch: bool,
    base_url: str,
    name: str,
    args: tuple[str],
) -> None:
    # Validate name, or download from URL
    # The second return value is an optional temporary directory. It is unused,
    # but must be kept around because its lifetime on disk is bound to the life
    # of the Python object
    name, _ = validate_name(name, allow_new_file=False, allow_directory=False)

    # correctness check - don't start the server if we can't import the module
    codegen.get_app(name)

    start(
        file_router=AppFileRouter.from_filename(name),
        development_mode=DEVELOPMENT_MODE,
        quiet=QUIET,
        host=host,
        port=port,
        headless=headless,
        mode=SessionMode.RUN,
        include_code=include_code,
        watch=watch,
        base_url=base_url,
        cli_args=parse_args(args),
    )


@main.command(help="Recover a marimo notebook from JSON.")
@click.argument("name", required=True)
def recover(name: str) -> None:
    path = pathlib.Path(name)
    if not os.path.exists(name):
        raise click.UsageError("Invalid NAME - %s does not exist" % name)

    if not path.is_file():
        raise click.UsageError("Invalid NAME - %s is not a file" % name)

    print(codegen.recover(name))


@main.command(
    help="""Open a tutorial.

marimo is a powerful library for making reactive notebooks
and apps. To get the most out of marimo, get started with a few
tutorials, starting with the intro:

    \b
    marimo tutorial intro

Recommended sequence:

    \b
    - intro
    - dataflow
    - ui
    - markdown
    - plots
    - layout
    - fileformat
    - for-jupyter-users
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
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.argument(
    "name",
    required=True,
    type=click.Choice(
        [
            "intro",
            "dataflow",
            "ui",
            "markdown",
            "plots",
            "layout",
            "fileformat",
            "for-jupyter-users",
        ]
    ),
)
def tutorial(
    port: Optional[int],
    host: str,
    headless: bool,
    name: Literal[
        "intro",
        "dataflow",
        "ui",
        "markdown",
        "plots",
        "layout",
        "fileformat",
        "for-jupyter-users",
    ],
) -> None:
    from marimo._tutorials import (
        dataflow,
        fileformat,
        intro,
        layout,
        marimo_for_jupyter_users,
        markdown,
        plots,
        ui,
    )

    tutorials = {
        "intro": intro,
        "dataflow": dataflow,
        "ui": ui,
        "markdown": markdown,
        "plots": plots,
        "layout": layout,
        "fileformat": fileformat,
        "for-jupyter-users": marimo_for_jupyter_users,
    }
    source = inspect.getsource(tutorials[name])
    d = tempfile.TemporaryDirectory()
    fname = os.path.join(d.name, name + ".py")
    with open(fname, "w", encoding="utf-8") as f:
        f.write(source)

    start(
        file_router=AppFileRouter.from_filename(fname),
        development_mode=DEVELOPMENT_MODE,
        quiet=QUIET,
        host=host,
        port=port,
        mode=SessionMode.EDIT,
        include_code=True,
        headless=headless,
        watch=False,
        cli_args={},
    )


@main.command()
@click.argument("ipynb", type=str, required=True)
def convert(ipynb: str) -> None:
    """Convert a Jupyter notebook to a marimo notebook.

    The argument may be either a path to a local .ipynb file,
    or an .ipynb file hosted on GitHub.

    Example usage:

        marimo convert your_nb.ipynb > your_nb.py

    After conversion, you can open the notebook in the editor:

        marimo edit your_nb.py

    Since marimo is different from traditional notebooks, once in the editor,
    you may need to fix errors like multiple definition errors or cycle
    errors.
    """
    print(ipynb_to_marimo.convert_from_path(ipynb))


@main.command()
def env() -> None:
    """Print out environment information for debugging purposes.

    Example usage:

        marimo env
    """
    print(json.dumps(get_system_info(), indent=2))


main.add_command(export)
