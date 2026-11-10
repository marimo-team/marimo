# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._config.manager import get_default_config_manager
from marimo._config.types import Theme


def get_current_theme() -> Theme:
    config = get_default_config_manager(current_path=None).get_config()
    return config.display.theme
