# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os

import click

from marimo._cli.config.utils import (
    format_config_docs,
    format_config_with_sources,
)
from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.print import echo
from marimo._config.manager import get_default_config_manager


@click.group(
    cls=ColoredGroup, help="""Various commands for the marimo config."""
)
def config() -> None:
    pass


@click.command(cls=ColoredCommand, help="""Show the marimo config.""")
@click.argument(
    "notebook", required=False, type=click.Path(exists=True, dir_okay=False)
)
def show(notebook: str | None = None) -> None:
    """
    Print out marimo config information.
    Example usage:

        marimo config show
    """
    config_manager = get_default_config_manager(
        current_path=notebook or os.getcwd()
    )
    echo("\nEffective configuration (sources shown in comments)\n")
    echo(format_config_with_sources(config_manager.get_config_with_sources()))


@click.command(cls=ColoredCommand, help="""Describe the marimo config.""")
def describe() -> None:
    """Print documentation for all config options."""
    from marimo._config.config_schema import MarimoConfig

    echo(format_config_docs(MarimoConfig))


config.add_command(show)
config.add_command(describe)
