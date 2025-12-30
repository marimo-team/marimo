# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from marimo._config.config import ExportType, SqlOutputType, WidthType

if TYPE_CHECKING:
    from marimo._config.manager import MarimoConfigManager


@dataclass
class AppDefaults:
    """Default configuration for app file managers."""

    width: Optional[WidthType] = None
    auto_download: Optional[list[ExportType]] = None
    sql_output: Optional[SqlOutputType] = None

    @staticmethod
    def from_config_manager(config: MarimoConfigManager) -> AppDefaults:
        return AppDefaults(
            width=config.default_width,
            auto_download=config.default_auto_download,
            sql_output=config.default_sql_output,
        )
