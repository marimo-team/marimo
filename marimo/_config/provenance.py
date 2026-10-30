# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig, PartialMarimoConfig

ConfigPath = tuple[str, ...]
ConfigSource: TypeAlias = (
    Path | Literal["env_var", "cli", "default", "inferred", "override"]
)


def env_var_name(path: ConfigPath) -> str:
    """Map supported settings to their existing environment variable names."""
    # Temporary until environment names are derived from schema paths.
    names: dict[ConfigPath, str] = {
        (
            "runtime",
            "auto_instantiate",
        ): "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE",
        ("runtime", "on_cell_change"): "MARIMO_RUNTIME_ON_CELL_CHANGE",
        ("runtime", "output_max_bytes"): "MARIMO_OUTPUT_MAX_BYTES",
        ("runtime", "std_stream_max_bytes"): "MARIMO_STD_STREAM_MAX_BYTES",
        ("server", "transport"): "MARIMO_SERVER_TRANSPORT",
        ("sharing", "html"): "MARIMO_RESTRICT_SHARING",
        ("sharing", "wasm"): "MARIMO_RESTRICT_SHARING",
        ("sharing", "molab"): "MARIMO_RESTRICT_SHARING",
    }
    return names[path]


def format_config_source(path: ConfigPath, source: ConfigSource) -> str:
    return env_var_name(path) if source == "env_var" else str(source)


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
