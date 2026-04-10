# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# tomllib is available in python 3.11+ and is much faster than tomlkit
# (C extension vs pure Python). Prefer it for read-only operations.
_HAS_TOMLLIB = sys.version_info >= (3, 11)


class TomlReader:
    """TOML reader that prefers tomllib (3.11+) over tomlkit."""

    decode_error: type[Exception]
    _load: Callable[[IO[bytes]], dict[str, Any]]
    _loads: Callable[[str], dict[str, Any]]

    def __init__(self) -> None:
        if _HAS_TOMLLIB:
            import tomllib

            self._load = tomllib.load  # type: ignore[assignment]
            self._loads = tomllib.loads  # type: ignore[assignment]
            self.decode_error = tomllib.TOMLDecodeError
        else:
            import tomlkit

            self._load = lambda f: tomlkit.load(f).unwrap()
            self._loads = lambda s: tomlkit.loads(s).unwrap()
            self.decode_error = tomlkit.exceptions.TOMLKitError

    def read(self, file_path: str | Path) -> dict[str, Any]:
        """Read and parse a TOML file."""
        with open(file_path, "rb") as file:
            return self._load(file)

    def reads(self, s: str) -> dict[str, Any]:
        """Read and parse a TOML string."""
        return self._loads(s)


toml_reader = TomlReader()
