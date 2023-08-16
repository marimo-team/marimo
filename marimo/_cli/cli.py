# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import pathlib
import tempfile
import urllib.request
from typing import Any, Literal, Optional

import click

from marimo import __version__, _loggers
from marimo._ast import codegen
from marimo._cli import ipynb_to_marimo
from marimo._server.server import start_server
from marimo._utils.url import is_url

DEVELOPMENT_MODE = False
QUIET = False


def colorize(string: str, color: Literal["red"]) -> str:
    if color == "red":
        color_code = "31"
    else:
        raise ValueError("Unrecognized color ", color)

    return f"\033[;{color_code}m{string}\033[0m"


def helpful_usage_error(self: Any, file: Any = None) -> None:
    if file is None:
        file = click.get_text_stream("stderr")
    color = None
    click.echo(
        colorize("Error", "red") + ": %s\n" % self.format_message(),
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
                    "create a notebook",
                ),
                (
                    "marimo edit app.py",
                    "create or edit a notebook called app.py",
                ),
                (
                    "marimo run app.py",
                    "run as a read-only app",
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
@click.version_option(version=__version__)
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
        "Edit a new or existing notebook.",
        _key_value_bullets(
            [
                (
                    "marimo edit",
                    "Create a new notebook",
                ),
                ("marimo edit app.py", "Create or edit app.py"),
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
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.argument("name", required=False)
def edit(
    port: Optional[int],
    headless: bool,
    name: Optional[str] = None,
) -> None:
    if name is not None:
        path = pathlib.Path(name)
        if path.suffix != ".py":
            raise click.UsageError(
                "Invalid NAME - %s is not a Python file" % name
            )

        if os.path.exists(name):
            if not path.is_file():
                raise click.UsageError(
                    "Invalid NAME - %s is not a file" % name
                )
            # module correctness check - don't start the server
            # if we can't import the module
            codegen.get_app(name)
        else:
            # write empty file
            try:
                with open(name, "w"):
                    pass
            except OSError:
                raise

    asyncio.run(
        start_server(
            development_mode=DEVELOPMENT_MODE,
            quiet=QUIET,
            port=port,
            headless=headless,
            filename=name,
            run=False,
        )
    )


@main.command(
    help="""Run as an app in read-only mode.

If NAME is a url, the app will be downloaded to a temporary file.

Example:

  \b
  * marimo run your_app.py
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
    "--headless",
    is_flag=True,
    default=False,
    show_default=True,
    type=bool,
    help="Don't launch a browser.",
)
@click.argument("name", required=True)
def run(port: Optional[int], headless: bool, name: str) -> None:
    path = pathlib.Path(name)
    if path.suffix != ".py":
        raise click.UsageError("Invalid NAME - %s is not a Python file" % name)

    if is_url(name):
        d = tempfile.TemporaryDirectory()
        logging.info("Downloading %s", name)
        path_to_app = os.path.join(d.name, os.path.basename(name))
        urllib.request.urlretrieve(url=name, filename=path_to_app)
        logging.info("App saved to %s", path_to_app)
        # overwrite name to point to the temporary file
        name = path_to_app
    elif not os.path.exists(name):
        raise click.UsageError("Invalid NAME - %s does not exist" % name)
    elif not path.is_file():
        raise click.UsageError("Invalid NAME - %s is not a file" % name)

    # correctness check - don't start the server if we can't import the module
    codegen.get_app(name)

    asyncio.run(
        start_server(
            development_mode=DEVELOPMENT_MODE,
            quiet=QUIET,
            port=port,
            headless=headless,
            filename=name,
            run=True,
        )
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

marimo is a powerful library for building interactive experiments
and dataflow apps. To get the most out of marimo, get started with a few
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
        ]
    ),
)
def tutorial(
    port: Optional[int],
    headless: bool,
    name: Literal[
        "intro", "dataflow", "ui", "markdown", "plots", "layout", "fileformat"
    ],
) -> None:
    from marimo._tutorials import (
        dataflow,
        fileformat,
        intro,
        layout,
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
    }
    source = inspect.getsource(tutorials[name])
    d = tempfile.TemporaryDirectory()
    fname = os.path.join(d.name, name + ".py")
    with open(fname, "w", encoding="utf-8") as f:
        f.write(source)

    asyncio.run(
        start_server(
            development_mode=DEVELOPMENT_MODE,
            quiet=QUIET,
            port=port,
            headless=headless,
            filename=fname,
            run=False,
        )
    )


@main.command()
@click.argument("ipynb", type=str, required=True)
def convert(ipynb: str) -> None:
    """Convert a Jupyter notebook to a marimo notebook.

    Example usage:

        marimo convert your_nb.ipynb > your_app.py

    After conversion, you can open the app in the editor:

        marimo edit your_app.py

    Since marimo is different from traditional notebooks, once in the editor,
    you may need to fix errors like multiple definition errors or cycle
    errors.
    """
    print(ipynb_to_marimo.convert(ipynb))
