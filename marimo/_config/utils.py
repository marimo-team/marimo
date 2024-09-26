# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional, cast

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_CONFIG,
    MarimoConfig,
    merge_default_config,
)

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


def _xdg_config_path() -> str:
    """Search XDG paths for marimo config file"""
    home_expansion = os.path.expanduser("~")
    home_directory = os.path.realpath(home_expansion)
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        home_directory, ".config"
    )
    return os.path.join(xdg_config_home, "marimo", "marimo.toml")


def get_or_create_config_path() -> str:
    """Find path of config file, or create it

    If no config file is found, one will be created under the proper XDG path
    (i.e. `~/.config/marimo` or `$XDG_CONFIG_HOME/marimo`)
    """
    current_config_path = get_config_path()
    if current_config_path:
        return current_config_path
    else:
        config_path = _xdg_config_path()
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        open(config_path, "a").close()
        return config_path


def get_config_path() -> Optional[str]:
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

    xdg_config_path = _xdg_config_path()
    if os.path.isfile(xdg_config_path):
        return xdg_config_path

    return None


def load_config() -> MarimoConfig:
    """Load configuration, taking into account user config file, if any."""
    try:
        path = get_config_path()
    except OSError as e:
        path = None
        msg = "Encountered error when searching for config: %s"
        LOGGER.warning(msg, str(e))

    if path is not None:
        LOGGER.debug("Using config at %s", path)
        try:
            import tomlkit

            with open(path, "rb") as f:
                user_config = tomlkit.parse(f.read())
        except Exception as e:
            LOGGER.error("Failed to read user config at %s", path)
            LOGGER.error(str(e))
            return DEFAULT_CONFIG
        return merge_default_config(cast(MarimoConfig, user_config))
    else:
        LOGGER.debug("No config found; loading default settings.")
    return DEFAULT_CONFIG
