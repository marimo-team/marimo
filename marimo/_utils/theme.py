# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._config.config import Theme
from marimo._config.manager import get_default_config_manager


def get_current_theme() -> Theme:
    """Return the current marimo theme from the default config manager."""
    config_manager = get_default_config_manager(current_path=None)
    return config_manager.theme
