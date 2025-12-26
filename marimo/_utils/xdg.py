# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path


def home_path() -> Path:
    """Get home directory or temp directory if home directory is not available.

    Returns:
        Path: The home directory.
    """
    try:
        return Path.home().resolve()
    except RuntimeError:
        # Can't get home directory, so use temp directory
        return Path("/tmp")


def xdg_config_home() -> Path:
    """Get XDG config home directory.

    Returns $XDG_CONFIG_HOME if set and non-empty, otherwise ~/.config
    """
    xdg_config_home_env = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home_env and xdg_config_home_env.strip():
        return Path(xdg_config_home_env)
    return home_path() / ".config"


def xdg_cache_home() -> Path:
    """Get XDG cache home directory.

    Returns $XDG_CACHE_HOME if set and non-empty, otherwise ~/.cache
    """
    xdg_cache_home_env = os.getenv("XDG_CACHE_HOME")
    if xdg_cache_home_env and xdg_cache_home_env.strip():
        return Path(xdg_cache_home_env)
    return home_path() / ".cache"


def xdg_state_home() -> Path:
    """Get XDG state home directory.

    Returns $XDG_STATE_HOME if set and non-empty, otherwise ~/.local/state
    """
    if os.name == "posix":
        xdg_state_home_env = os.getenv("XDG_STATE_HOME")
        if xdg_state_home_env and xdg_state_home_env.strip():
            return Path(xdg_state_home_env)
        return home_path() / ".local" / "state"
    else:
        return home_path()


def marimo_config_path() -> Path:
    """Get marimo config file path using XDG specification.

    $XDG_CONFIG_HOME/marimo/marimo.toml if set, otherwise ~/.config/marimo/marimo.toml
    """
    return xdg_config_home() / "marimo" / "marimo.toml"


def marimo_cache_dir() -> Path:
    """Get marimo cache directory using XDG specification.

    $XDG_CACHE_HOME/marimo if set, otherwise ~/.cache/marimo
    """
    return xdg_cache_home() / "marimo"


def marimo_state_dir() -> Path:
    """Get marimo state directory using XDG specification.

    On Linux/macOS/Unix, returns:
    $XDG_STATE_HOME/marimo if set, otherwise ~/.local/state/marimo

    On Windows, returns:
    ~/.marimo
    """
    if os.name == "posix":
        return xdg_state_home() / "marimo"
    else:
        return home_path() / ".marimo"


def marimo_log_dir() -> Path:
    """Get marimo log directory using XDG specification.

    $XDG_CACHE_HOME/marimo/logs if set, otherwise ~/.cache/marimo/logs
    """
    return marimo_cache_dir() / "logs"
