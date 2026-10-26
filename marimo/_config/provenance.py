# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig, PartialMarimoConfig

ConfigPath = tuple[str, ...]
ConfigSource: TypeAlias = (
    Path
    | Literal[
        "env_var",
        "cli",
        "default",
        "inferred",
        "override",
        "MARIMO_RESTRICT_SHARING",
    ]
)


def env_var_name(path: ConfigPath) -> str:
    """Name the environment variable supplying a setting or collection entry."""
    from marimo._config.config_schema import MarimoConfig
    from marimo._config.schema_utils import config_leaf_types

    leaves = config_leaf_types(MarimoConfig)
    for length in range(1, len(path) + 1):
        if path[:length] in leaves:
            return "MARIMO_" + "_".join(path[:length]).upper()
    return "MARIMO_" + "_".join(path).upper()


def format_config_source(path: ConfigPath, source: ConfigSource) -> str:
    if source == "env_var":
        return f"env var: {env_var_name(path)}"
    if source == "MARIMO_RESTRICT_SHARING":
        return f"env var: {source}"
    return str(source)


@dataclass
class ConfigLayer:
    """Sparse settings from a single source."""

    config: PartialMarimoConfig
    source: ConfigSource


@dataclass
class ResolvedConfig:
    """Effective settings with provenance kept separate from their values."""

    config: MarimoConfig
    origins: dict[ConfigPath, ConfigSource]
