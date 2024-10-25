# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.from_panel import panel as from_panel


class PanelFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "panel"

    def register(self) -> None:
        import panel  # type: ignore
        import param  # type: ignore

        from marimo._output import formatting

        @formatting.formatter(param.reactive.rx)
        @formatting.formatter(panel.viewable.Viewable)
        @formatting.formatter(panel.viewable.Viewer)
        def _from(lmap: Any) -> tuple[KnownMimeType, str]:
            return from_panel(lmap)._mime_()
