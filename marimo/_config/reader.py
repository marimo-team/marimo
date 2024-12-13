# Copyright 2024 Marimo. All rights reserved.
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import PartialMarimoConfig

LOGGER = _loggers.marimo_logger()


def read_toml(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read and parse a TOML file."""
    import tomlkit

    with open(file_path, "rb") as file:
        return tomlkit.load(file)


def read_marimo_config(path: str) -> PartialMarimoConfig:
    """Read the marimo.toml configuration."""
    return cast(PartialMarimoConfig, read_toml(path))


def read_pyproject_config(
    start_path: Union[str, Path],
) -> Optional[PartialMarimoConfig]:
    """Read the pyproject.toml configuration."""
    path = find_nearest_pyproject_toml(start_path)
    if path is None:
        return None
    pyproject_config = read_toml(path)
    marimo_tool_config = pyproject_config.get("tool", {}).get("marimo", None)
    if marimo_tool_config is None:
        return None
    if not isinstance(marimo_tool_config, dict):
        LOGGER.warning(
            "pyproject.toml contains invalid marimo config: %s",
            marimo_tool_config,
        )
        return None
    LOGGER.debug("Found marimo config in pyproject.toml at %s", path)
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
