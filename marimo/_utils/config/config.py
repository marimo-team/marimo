# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, TypeVar

from marimo._utils.parse_dataclass import parse_raw
from marimo._utils.toml import is_toml_error, read_toml
from marimo._utils.xdg import home_path, marimo_state_dir

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
        home_directory = ConfigReader._get_home_directory()
        filepath = home_directory / ROOT_DIR / filename
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

        self.filepath.write_text(tomlkit.dumps(dict_data))

    @staticmethod
    def _get_home_directory() -> Path:
        # If in pytest, we want to set a temporary directory
        if os.environ.get("PYTEST_CURRENT_TEST"):
            # If the home directory is given by test, take it
            home_dir = os.environ.get("MARIMO_PYTEST_HOME_DIR")
            if home_dir is not None:
                return Path(home_dir)
            else:
                tmpdir = TemporaryDirectory()
                return Path(tmpdir.name)
        else:
            return home_path()
