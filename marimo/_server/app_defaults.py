# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._config.config import ExportType, SqlOutputType, WidthType

if TYPE_CHECKING:
    from marimo._config.manager import MarimoConfigManager


@dataclass
class AppDefaults:
    """Default configuration for app file managers."""

    width: WidthType | None = None
    auto_download: list[ExportType] | None = None
    sql_output: SqlOutputType | None = None

    @staticmethod
    def from_config_manager(config: MarimoConfigManager) -> AppDefaults:
        return AppDefaults(
            width=config.default_width,
            auto_download=config.default_auto_download,
            sql_output=config.default_sql_output,
        )
