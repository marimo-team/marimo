# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os

import click

from marimo._cli.config.utils import (
    format_config_docs,
    highlight_toml_headers,
)
from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._cli.print import echo, green
from marimo._config.manager import (
    UserConfigStore,
    get_default_config_manager,
)
from marimo._config.reader import find_nearest_pyproject_toml


@click.group(
    cls=ColoredGroup, help="""Various commands for the marimo config."""
)
def config() -> None:
    pass


@click.command(cls=ColoredCommand, help="""Show the marimo config.""")
def show() -> None:
    """
    Print out marimo config information.
    Example usage:

        marimo config show
    """
    import tomlkit

    current_path = os.getcwd()

    config_manager = get_default_config_manager(current_path=current_path)
    # Save config if doesn't exist
    UserConfigStore().save_config_if_missing()

    # Show project overrides if they exist
    project_config_path = find_nearest_pyproject_toml(current_path)
    overrides = config_manager.get_config_overrides()
    if overrides:
        echo(
            f"\n📁 Project overrides from {green(str(project_config_path))}\n"
        )
        echo(highlight_toml_headers(tomlkit.dumps(overrides)))

    # Show user config
    user_config_path = config_manager.user_config_mgr.get_config_path()
    echo(f"\n🏠 User config from {green(user_config_path)}\n")
    user_config = config_manager.get_user_config()
    echo(highlight_toml_headers(tomlkit.dumps(user_config)))


@click.command(cls=ColoredCommand, help="""Describe the marimo config.""")
def describe() -> None:
    """Print documentation for all config options."""
    from marimo._config.config_schema import MarimoConfig

    echo(format_config_docs(MarimoConfig))


config.add_command(show)
config.add_command(describe)
