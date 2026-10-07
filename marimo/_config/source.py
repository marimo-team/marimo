# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Protocol

from marimo._config.config import MarimoConfig, PartialMarimoConfig


class ConfigReader(Protocol):
    """Read one configuration surface without resolving other sources."""

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        """Read explicit values, masking secrets by default."""
        ...


class ConfigStore(ConfigReader, Protocol):
    """A configuration source that also supports persistent changes."""

    def update(self, patch: PartialMarimoConfig | MarimoConfig) -> None:
        """Persist an update using the store's merge semantics."""
        ...

    def unset(self, path: tuple[str, ...]) -> None:
        """Remove a stored setting so its fallback can apply."""
        ...
