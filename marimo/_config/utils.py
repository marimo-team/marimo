# Copyright 2023 Marimo. All rights reserved.
import os
from typing import Optional, cast

import tomlkit

from marimo import _loggers
from marimo._config.config import MarimoConfig, configure, get_configuration

LOGGER = _loggers.marimo_logger()


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


def get_config_path() -> Optional[str]:
    """Find path of config file (.marimo.toml).

    Searches from current directory to home, return the first config file
    found, if Any.

    If current directory isn't contained in home, just searches current
    directory and home.

    May raise an OSError.
    """
    filename = ".marimo.toml"

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
        config_path = _check_directory_for_file(current_directory, filename)
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
            config_path = os.path.join(current_directory, filename)
            if os.path.isfile(config_path):
                return config_path
            else:
                current_directory = os.path.realpath(
                    os.path.dirname(current_directory)
                )

    config_path = os.path.join(home_directory, filename)
    if os.path.isfile(config_path):
        return config_path

    return None


def load_config() -> Optional[MarimoConfig]:
    """Load configuration, taking into account user config file, if any."""
    try:
        path = get_config_path()
    except OSError as e:
        path = None
        LOGGER.warn("Encountered error when searching for config: %s", str(e))

    if path is not None:
        LOGGER.debug("Using config at %s", path)
        try:
            with open(path, "rb") as f:
                user_config = tomlkit.parse(f.read())
        except Exception as e:
            LOGGER.error("Failed to read user config at %s", path)
            LOGGER.error(str(e))
            return get_configuration()
        configure(cast(MarimoConfig, user_config))
    else:
        LOGGER.debug("No config found; loading default settings.")
    return get_configuration()
