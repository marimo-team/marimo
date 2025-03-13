# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from pathlib import Path


def read_toml(file_path: Union[str, Path]) -> dict[str, Any]:
    """Read and parse a TOML file."""
    import tomlkit

    with open(file_path, "rb") as file:
        return tomlkit.load(file)
