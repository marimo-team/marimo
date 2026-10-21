# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig, PartialMarimoConfig

ConfigPath = tuple[str, ...]


@dataclass(frozen=True)
class ConfigSource:
    """The source of an explicitly supplied value or a default."""

    kind: Literal[
        "default",
        "user",
        "project",
        "script",
        "environment",
        "override",
        "inferred",
        "security",
    ]
    location: str | None = None

    def __str__(self) -> str:
        return f"{self.kind}: {self.location}" if self.location else self.kind


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
