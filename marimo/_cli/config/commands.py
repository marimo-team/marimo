# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import click

from marimo._cli.config.utils import highlight_toml_headers
from marimo._cli.print import echo, green
from marimo._config.manager import UserConfigManager


@click.group(help="""Various commands for the marimo config.""")
def config() -> None:
    pass


@click.command(help="""Show the marimo config""")
def show() -> None:
    """
    Print out marimo config information.
    Example usage:

        marimo config show
    """
    import tomlkit

    config_manager = UserConfigManager()
    # Save config if doesn't exist
    config_manager.save_config_if_missing()
    echo(f"User config from {green(config_manager.get_config_path())}\n")
    toml_string = tomlkit.dumps(config_manager.get_config())
    echo(highlight_toml_headers(toml_string))


config.add_command(show)
