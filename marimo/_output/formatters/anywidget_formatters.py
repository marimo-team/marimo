# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.from_anywidget import from_anywidget


class AnyWidgetFormatter(FormatterFactory):
    """Formatter factory for anywidget AnyWidget objects."""

    @staticmethod
    def package_name() -> str:
        """Return the package name this formatter handles."""
        return "anywidget"

    def register(self) -> None:
        """Register formatter that converts anywidget.AnyWidget to a marimo UI element."""
        import anywidget  # type: ignore [import-not-found]

        from marimo._output import formatting

        @formatting.formatter(anywidget.AnyWidget)
        def _from(lmap: anywidget.AnyWidget) -> tuple[KnownMimeType, str]:
            return from_anywidget(lmap)._mime_()
