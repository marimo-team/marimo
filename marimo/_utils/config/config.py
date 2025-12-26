# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, TypeVar

from marimo._utils.parse_dataclass import parse_raw
from marimo._utils.toml import is_toml_error, read_toml
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from pathlib import Path

ROOT_DIR = marimo_state_dir()

T = TypeVar("T")


class ConfigReader:
    """Read the configuration file.

    Read/writes state to $XDG_STATE_HOME/marimo or ~/.local/state/marimo
    """

    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath

    @staticmethod
    def for_filename(filename: str) -> ConfigReader:
        filepath = ROOT_DIR / filename
        return ConfigReader(filepath)

    def read_toml(self, cls: type[T], *, fallback: T) -> T:
        try:
            data = read_toml(self.filepath)
            return parse_raw(data, cls, allow_unknown_keys=True)
        except Exception as e:
            if is_toml_error(e) or isinstance(e, FileNotFoundError):
                return fallback
            raise e

    def write_toml(self, data: Any) -> None:
        import tomlkit

        self.filepath.parent.mkdir(parents=True, exist_ok=True)

        dict_data = asdict(data)
        # None values is not valid toml, so we remove them
        dict_data = {k: v for k, v in dict_data.items() if v is not None}

        self.filepath.write_text(tomlkit.dumps(dict_data), encoding="utf-8")
