# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

import click

from marimo._cli.config.utils import highlight_toml_headers
from marimo._cli.print import echo, green
from marimo._config.manager import (
    UserConfigManager,
    get_default_config_manager,
)
from marimo._config.reader import find_nearest_pyproject_toml


@click.group(help="""Various commands for the marimo config.""")
def config() -> None:
    pass


@click.command(help="""Show the marimo config.""")
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
    UserConfigManager().save_config_if_missing()

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


@click.command(help="""Describe the marimo config.""")
def describe() -> None:
    """Print documentation for all config options."""
    import inspect
    from textwrap import indent

    import marimo._config.config as marimo_config
    from marimo._cli.print import echo, green, muted, yellow

    def format_type_docs(cls: type, indent_level: int = 0) -> str:
        """Recursively format type documentation."""
        output: list[str] = []
        # Get annotations and docs from the class
        annotations = (
            cls.__annotations__ if hasattr(cls, "__annotations__") else {}
        )

        # Get the docstring
        doc = inspect.getdoc(cls)
        if doc and indent_level == 0:
            output.append(muted(f"# {doc}\n"))

        for key, type_hint in annotations.items():
            # Get field documentation if available
            if hasattr(type_hint, "__forward_arg__"):
                type_hint = type_hint.__forward_arg__
                # Import from marimo._config.config
                # If NotRequired, we need to get the type from the NotRequired
                if str(type_hint).startswith("NotRequired["):
                    type_hint = type_hint[12:-1]

                if type_hint in marimo_config.__dict__ and "TypedDict" in str(
                    type(marimo_config.__dict__[type_hint])
                ):
                    config = marimo_config.__dict__[type_hint]
                    field_output = f"[{green(key)}]"
                    output.append(indent(field_output, "  " * indent_level))
                    # Get the docstring for the nested TypedDict
                    nested_doc = inspect.getdoc(config)
                    if nested_doc:
                        output.append(
                            indent(
                                muted(f"# {nested_doc}"),
                                "  " * (indent_level + 1),
                            )
                        )
                        output.append("")
                    output.append(
                        indent(
                            format_type_docs(config, indent_level + 1),
                            "  " * indent_level,
                        )
                    )
                else:
                    output.append(
                        indent(
                            f"{yellow(key)}: {type_hint}", "  " * indent_level
                        )
                    )
                    output.append("")
            else:
                field_output = f"{yellow(key)}: {type_hint}"
                output.append(indent(field_output, "  " * indent_level))

        return "\n".join(output)

    echo(format_type_docs(marimo_config.MarimoConfig))


config.add_command(show)
config.add_command(describe)
