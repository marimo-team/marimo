# Copyright 2024 Marimo. All rights reserved.
import os
from dataclasses import asdict
from tempfile import TemporaryDirectory
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
        home_expansion = ConfigReader._get_home_directory()
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

    @staticmethod
    def _get_home_directory() -> str:
        # If in pytest, we want to set a temporary directory
        if os.environ.get("PYTEST_CURRENT_TEST"):
            tmpdir = TemporaryDirectory()
            return tmpdir.name
        else:
            return os.path.expanduser("~")


def _maybe_create_directory(file_path: str) -> None:
    marimo_directory = os.path.dirname(file_path)
    if not os.path.exists(marimo_directory):
        os.makedirs(marimo_directory)
