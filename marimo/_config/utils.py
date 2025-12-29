# Copyright 2026 Marimo. All rights reserved.
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
    try:
        current_config_path = get_user_config_path()
        if current_config_path:
            return current_config_path
    except OSError as e:
        # Handle OSError that can occur on Windows when os.path.realpath()
        # fails due to issues like deleted directory, permission problems,
        # UNC path issues, or special characters in path.
        # See https://github.com/marimo-team/marimo/issues/7502
        LOGGER.error(
            "Could not search for config file due to path error: %s. "
            "Falling back to XDG config path.",
            str(e),
        )

    # No config found or error occurred, create XDG config
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

    Searches from current directory up through all parent directories,
    then checks home directory, then XDG paths.

    Returns the first config file found, if any.

    May raise an OSError.
    """

    # we use os.path.realpath to canonicalize paths, just in case
    # some these functions don't eliminate symlinks on some platforms
    current_directory = os.path.realpath(os.getcwd())
    home_expansion = os.path.expanduser("~")
    home_directory = None
    if home_expansion != "~":
        home_directory = os.path.realpath(home_expansion)

    # Track whether we've already checked home during parent traversal
    checked_home = False

    # Traverse parent directories, stopping at home if under home
    previous_directory = None
    search_directory = current_directory
    while search_directory != previous_directory:
        previous_directory = search_directory
        config_path = _check_directory_for_file(
            search_directory, CONFIG_FILENAME
        )
        if config_path is not None:
            return config_path

        # Stop at home directory if we're under it
        if search_directory == home_directory:
            checked_home = True
            break

        search_directory = os.path.realpath(os.path.dirname(search_directory))

    # Check home directory if not already checked during traversal
    # (happens when cwd is not under home)
    if home_directory and not checked_home:
        config_path = _check_directory_for_file(
            home_directory, CONFIG_FILENAME
        )
        if config_path is not None:
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
