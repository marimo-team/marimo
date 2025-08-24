# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional

from marimo import _loggers
from marimo._utils.xdg import marimo_config_path

LOGGER = _loggers.marimo_logger()

CONFIG_FILENAME = ".marimo.toml"


def _is_parent(parent_path: str, child_path: str) -> bool:
    # Check if parent is actually a parent of child
    # paths must be real/absolute paths
    try:
        return os.path.commonpath([parent_path]) == os.path.commonpath(
            [parent_path, child_path]
        )
    except Exception:
        return False


def _check_directory_for_file(directory: str, filename: str) -> Optional[str]:
    config_path = os.path.join(directory, filename)
    if os.path.isfile(config_path):
        return config_path
    return None


def get_or_create_user_config_path() -> str:
    """Find path of config file, or create it

    If no config file is found, one will be created under the proper XDG path
    (i.e. `~/.config/marimo` or `$XDG_CONFIG_HOME/marimo`)
    """
    current_config_path = get_user_config_path()
    if current_config_path:
        return current_config_path
    else:
        config_path = marimo_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # Create an empty file
        config_path.touch()
        return str(config_path)


# This operation may be expensive due to searching for a config file up to
# the home directory.
# We cache the result to avoid re-searching. It is ok to expect new
# config files to only be picked up after a restart.
@lru_cache(maxsize=1)
def get_user_config_path() -> Optional[str]:
    """Find path of config file (.marimo.toml).

    Searches from current directory to home, return the first config file
    found, if Any.

    If current directory isn't contained in home, just searches current
    directory and home.

    If not found between current directory and home, will search XDG paths
    (i.e. `~/.config/marimo` and `$XDG_CONFIG_HOME/marimo`).

    May raise an OSError.
    """

    # we use os.path.realpath to canonicalize paths, just in case
    # some these functions don't eliminate symlinks on some platforms
    current_directory = os.path.realpath(os.getcwd())
    home_expansion = os.path.expanduser("~")
    if home_expansion == "~":
        # path expansion failed
        return None
    home_directory = os.path.realpath(home_expansion)

    if not _is_parent(home_directory, current_directory):
        # Can't search back to home, since current_directory not in
        # home_directory
        config_path = _check_directory_for_file(
            current_directory, CONFIG_FILENAME
        )
        if config_path is not None:
            return config_path
    else:
        previous_directory = None
        # Search up to home; terminate when at home or at a fixed point
        while (
            current_directory != home_directory
            and current_directory != previous_directory
        ):
            previous_directory = current_directory
            config_path = os.path.join(current_directory, CONFIG_FILENAME)
            if os.path.isfile(config_path):
                return config_path
            else:
                current_directory = os.path.realpath(
                    os.path.dirname(current_directory)
                )

    config_path = os.path.join(home_directory, CONFIG_FILENAME)
    if os.path.isfile(config_path):
        return config_path

    xdg_config_path = marimo_config_path()
    if xdg_config_path.is_file():
        return str(xdg_config_path)

    return None


def deep_copy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: deep_copy(v) for k, v in obj.items()}  # type: ignore
    if isinstance(obj, list):
        return [deep_copy(v) for v in obj]  # type: ignore
    return obj
