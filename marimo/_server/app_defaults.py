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
    # PEP 723 header string to set on new notebooks
    header: Optional[str] = None

    @staticmethod
    def from_config_manager(config: MarimoConfigManager) -> AppDefaults:
        return AppDefaults(
            width=config.default_width,
            auto_download=config.default_auto_download,
            sql_output=config.default_sql_output,
        )

    @staticmethod
    def from_url_params(
        base: AppDefaults,
        url_params: dict[str, str],
    ) -> AppDefaults:
        """Create AppDefaults by merging URL params into a base.

        Builds a PEP 723 header string from the URL params and stores it
        in the header field for serialization into new notebooks.

        Args:
            base: The base AppDefaults (typically from config manager)
            url_params: URL parameters extracted from the request

        Returns:
            New AppDefaults with header built from URL params
        """
        from marimo._server.url_params import build_header_from_params

        header = build_header_from_params(url_params)

        return AppDefaults(
            width=base.width,
            auto_download=base.auto_download,
            sql_output=base.sql_output,
            header=header,
        )
