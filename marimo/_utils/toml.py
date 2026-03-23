# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from pathlib import Path

# tomllib is available in python 3.11+ and is much faster than tomlkit
# (C extension vs pure Python). Prefer it for read-only operations.
_HAS_TOMLLIB = sys.version_info >= (3, 11)


def read_toml(file_path: Union[str, Path]) -> dict[str, Any]:
    """Read and parse a TOML file."""

    if _HAS_TOMLLIB:
        import tomllib

        with open(file_path, "rb") as file:
            return tomllib.load(file)
    else:
        import tomlkit

        with open(file_path, "rb") as file:
            return tomlkit.load(file).unwrap()


def read_toml_string(s: str) -> dict[str, Any]:
    """Read and parse a TOML string."""

    if _HAS_TOMLLIB:
        import tomllib

        return tomllib.loads(s)
    else:
        import tomlkit

        return tomlkit.loads(s).unwrap()


def is_toml_error(e: Exception) -> bool:
    """Check if an exception is a TOML error."""

    if _HAS_TOMLLIB:
        import tomllib

        return isinstance(e, tomllib.TOMLDecodeError)
    else:
        import tomlkit

        return isinstance(e, tomlkit.exceptions.TOMLKitError)
