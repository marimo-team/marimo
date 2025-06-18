# Copyright 2024 Marimo. All rights reserved.

from marimo._config.config import Theme
from marimo._config.manager import get_default_config_manager


def get_current_theme() -> Theme:
    config_manager = get_default_config_manager(current_path=None)
    return config_manager.theme
