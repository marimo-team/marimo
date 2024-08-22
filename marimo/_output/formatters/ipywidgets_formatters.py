# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.anywidget.init import init_marimo_widget


class IPyWidgetsFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "ipywidgets"

    def register(self) -> None:
        import ipywidgets  # type:ignore

        Widget = ipywidgets.Widget
        Widget.on_widget_constructed(init_marimo_widget)  # type:ignore
