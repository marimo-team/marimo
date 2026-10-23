# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NewType, TypeAlias

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig, PartialMarimoConfig

ConfigPath = tuple[str, ...]
EnvVarName = NewType("EnvVarName", str)
ConfigSource: TypeAlias = (
    Path | EnvVarName | Literal["cli", "default", "inferred", "override"]
)


@dataclass
class ConfigLayer:
    """A sparse configuration and the sources of its values."""

    config: PartialMarimoConfig
    source: ConfigSource
    origins: dict[ConfigPath, ConfigSource] = field(default_factory=dict)


@dataclass
class ResolvedConfig:
    """Effective settings with provenance kept separate from their values."""

    config: MarimoConfig
    origins: dict[ConfigPath, ConfigSource]
