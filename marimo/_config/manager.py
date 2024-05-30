# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional

from marimo import _loggers
from marimo._config.config import (
    MarimoConfig,
    mask_secrets,
    merge_config,
    merge_default_config,
    remove_secret_placeholders,
)
from marimo._config.utils import CONFIG_FILENAME, get_config_path, load_config

LOGGER = _loggers.marimo_logger()


class UserConfigManager:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path
        self.config = load_config()

    def save_config(self, config: MarimoConfig) -> MarimoConfig:
        import tomlkit

        config_path = self.get_config_path()
        LOGGER.debug("Saving user configuration to %s", config_path)
        # Remove the secret placeholders from the incoming config
        config = remove_secret_placeholders(config)
        # Merge the current config with the new config
        merged = merge_config(self.config, config)

        with open(config_path, "w", encoding="utf-8") as f:
            tomlkit.dump(merged, f)

        self.config = merge_default_config(merged)
        return self.config

    def get_config(self, hide_secrets: bool = True) -> MarimoConfig:
        if hide_secrets:
            return mask_secrets(self.config)
        return self.config

    def get_config_path(self) -> str:
        return get_config_path() or self._default_config_path()

    def _default_config_path(self) -> str:
        home = os.path.expanduser("~")
        return os.path.join(home, CONFIG_FILENAME)
