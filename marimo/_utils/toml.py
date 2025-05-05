# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from pathlib import Path


def read_toml(file_path: Union[str, Path]) -> dict[str, Any]:
    """Read and parse a TOML file."""

    # Prefer tomllib over tomlkit for reading since it is built-in and works with pyodide
    # tomllib is only available in python 3.11+
    if DependencyManager.tomllib.has():
        import tomllib

        with open(file_path, "rb") as file:
            return tomllib.load(file)
    else:
        import tomlkit

        with open(file_path, "rb") as file:
            return tomlkit.load(file)


def read_toml_string(s: str) -> dict[str, Any]:
    """Read and parse a TOML string."""

    # Prefer tomllib over tomlkit for reading since it is built-in and works with pyodide
    # tomllib is only available in python 3.11+
    if DependencyManager.tomllib.has():
        import tomllib

        return tomllib.loads(s)
    else:
        import tomlkit

        return tomlkit.loads(s)


def is_toml_error(e: Exception) -> bool:
    """Check if an exception is a TOML error."""
    if DependencyManager.tomllib.has():
        import tomllib

        return isinstance(e, tomllib.TOMLDecodeError)
    else:
        import tomlkit

        return isinstance(e, tomlkit.exceptions.TOMLKitError)
