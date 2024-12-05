# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_CONFIG,
    MarimoConfig,
    PartialMarimoConfig,
    mask_secrets,
    merge_config,
    merge_default_config,
    remove_secret_placeholders,
)
from marimo._config.utils import (
    get_or_create_config_path,
    load_config,
)

LOGGER = _loggers.marimo_logger()


class UserConfigManager:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path
        self._config = load_config()

    def save_config(
        self, config: MarimoConfig | PartialMarimoConfig
    ) -> MarimoConfig:
        import tomlkit

        config_path = self.get_config_path()
        LOGGER.debug("Saving user configuration to %s", config_path)
        # Remove the secret placeholders from the incoming config
        config = remove_secret_placeholders(config)
        # Merge the current config with the new config
        merged = merge_config(self._config, config)

        with open(config_path, "w", encoding="utf-8") as f:
            tomlkit.dump(merged, f)

        self._config = merge_default_config(merged)
        return self._config

    def save_config_if_missing(self) -> None:
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                self.save_config(DEFAULT_CONFIG)
        except Exception as e:
            LOGGER.warning("Failed to save config: %s", e)

    def get_config(self, hide_secrets: bool = True) -> MarimoConfig:
        if hide_secrets:
            return mask_secrets(self._config)
        return self._config

    def get_config_path(self) -> str:
        return get_or_create_config_path()


class UserConfigManagerWithOverride(UserConfigManager):
    def __init__(
        self, delegate: UserConfigManager, override_config: PartialMarimoConfig
    ) -> None:
        self.delegate = delegate
        self.override_config = override_config

    def get_config(self, hide_secrets: bool = True) -> MarimoConfig:
        return merge_config(
            self.delegate.get_config(hide_secrets), self.override_config
        )
