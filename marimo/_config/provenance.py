# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig, PartialMarimoConfig

ConfigPath = tuple[str, ...]

# Compatibility aliases scheduled for removal in marimo 1.0.
DEPRECATED_ENV_VARS: dict[ConfigPath, str] = {
    (
        "runtime",
        "auto_instantiate",
    ): "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE",
    ("runtime", "output_max_bytes"): "MARIMO_OUTPUT_MAX_BYTES",
    ("runtime", "std_stream_max_bytes"): "MARIMO_STD_STREAM_MAX_BYTES",
    ("runtime", "sql_default_limit"): "MARIMO_SQL_DEFAULT_LIMIT",
    ("server", "skip_update_check"): "MARIMO_SKIP_UPDATE_CHECK",
    ("server", "session_cookie_secure"): "MARIMO_SESSION_COOKIE_SECURE",
    ("server", "session_secret"): "MARIMO_SESSION_SECRET",
}
ConfigSource: TypeAlias = (
    Path
    | Literal[
        "env_var",
        "deprecated_env_var",
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
    if source == "deprecated_env_var":
        return f"env var: {DEPRECATED_ENV_VARS[path]} (deprecated)"
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

    @property
    def override_paths(self) -> tuple[ConfigPath, ...]:
        """Settings explicitly overridden above file and environment sources."""
        return tuple(
            path
            for path, source in self.origins.items()
            if source in ("override", "cli")
        )
