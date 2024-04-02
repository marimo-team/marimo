# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.from_anywidget import from_anywidget


class AnyWidgetFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "anywidget"

    def register(self) -> None:
        import anywidget  # type: ignore [import-not-found]

        from marimo._output import formatting

        @formatting.formatter(anywidget.AnyWidget)
        def _from(lmap: anywidget.AnyWidget) -> tuple[KnownMimeType, str]:
            return from_anywidget(lmap)._mime_()
