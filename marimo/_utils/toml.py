# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tomllib
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class TomlReader:
    """Read-only TOML reader backed by the standard library `tomllib`."""

    decode_error: type[Exception]
    _load: Callable[[IO[bytes]], dict[str, Any]]
    _loads: Callable[[str], dict[str, Any]]

    def __init__(self) -> None:
        self._load = tomllib.load
        self._loads = tomllib.loads
        self.decode_error = tomllib.TOMLDecodeError

    def read(self, file_path: str | Path) -> dict[str, Any]:
        """Read and parse a TOML file."""
        with open(file_path, "rb") as file:
            return self._load(file)

    def reads(self, s: str) -> dict[str, Any]:
        """Read and parse a TOML string."""
        return self._loads(s)


toml_reader = TomlReader()
