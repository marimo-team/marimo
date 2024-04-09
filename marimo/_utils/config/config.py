import os
from dataclasses import asdict
from typing import Any, Optional, Type, TypeVar

import tomlkit

from marimo._utils.parse_dataclass import parse_raw

ROOT_DIR = ".marimo"

T = TypeVar("T")


class ConfigReader:
    """Read the configuration file."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    @staticmethod
    def for_filename(filename: str) -> Optional["ConfigReader"]:
        home_expansion = os.path.expanduser("~")
        if home_expansion == "~":
            # path expansion failed
            return None
        home_directory = os.path.realpath(home_expansion)
        filepath = os.path.join(home_directory, ROOT_DIR, filename)
        return ConfigReader(filepath)

    def read_toml(self, cls: Type[T], *, fallback: T) -> T:
        try:
            with open(self.filepath, "r") as file:
                data = tomlkit.parse(file.read())
                return parse_raw(data, cls)
        except FileNotFoundError:
            return fallback

    def write_toml(self, data: Any) -> None:
        _maybe_create_directory(self.filepath)
        with open(self.filepath, "w") as file:
            tomlkit.dump(asdict(data), file)


def _maybe_create_directory(file_path: str) -> None:
    marimo_directory = os.path.dirname(file_path)
    if not os.path.exists(marimo_directory):
        os.makedirs(marimo_directory)
