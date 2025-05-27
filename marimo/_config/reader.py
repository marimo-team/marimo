# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import PartialMarimoConfig
from marimo._utils.toml import read_toml

LOGGER = _loggers.marimo_logger()


def read_marimo_config(path: str) -> PartialMarimoConfig:
    """Read the marimo.toml configuration."""
    return cast(PartialMarimoConfig, read_toml(path))


def read_pyproject_marimo_config(
    pyproject_path: Union[str, Path],
) -> Optional[PartialMarimoConfig]:
    """Read the marimo tool config from a pyproject.toml file."""
    pyproject_config = read_toml(pyproject_path)
    marimo_tool_config = get_marimo_config_from_pyproject_dict(
        pyproject_config
    )
    if marimo_tool_config is None:
        return None
    LOGGER.info("Found marimo config in pyproject.toml at %s", pyproject_path)
    return marimo_tool_config


def get_marimo_config_from_pyproject_dict(
    pyproject_dict: dict[str, Any],
) -> Optional[PartialMarimoConfig]:
    """Get the marimo config from a pyproject.toml dictionary."""
    marimo_tool_config = pyproject_dict.get("tool", {}).get("marimo", None)
    if marimo_tool_config is None:
        return None
    if not isinstance(marimo_tool_config, dict):
        LOGGER.warning(
            "pyproject.toml contains invalid marimo config: %s",
            marimo_tool_config,
        )
        return None
    return cast(PartialMarimoConfig, marimo_tool_config)


def find_nearest_pyproject_toml(
    start_path: Union[str, Path],
) -> Optional[Path]:
    """Find the nearest pyproject.toml file."""
    path = Path(start_path)
    root = path.anchor
    while not path.joinpath("pyproject.toml").exists():
        if str(path) == root:
            return None
        if path.parent == path:
            return None
        path = path.parent
    return path.joinpath("pyproject.toml")
