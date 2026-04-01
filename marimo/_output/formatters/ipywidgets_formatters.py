# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.anywidget.init import init_marimo_widget


class IPyWidgetsFormatter(FormatterFactory):
    """Formatter factory that integrates ipywidgets with marimo."""

    @staticmethod
    def package_name() -> str:
        """Return the package name this formatter handles."""
        return "ipywidgets"

    def register(self) -> None:
        """Register marimo's widget initializer as an ipywidgets construction callback."""
        import ipywidgets  # type:ignore

        Widget = ipywidgets.Widget
        Widget.on_widget_constructed(init_marimo_widget)  # type:ignore
