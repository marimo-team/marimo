# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._config.config import Theme
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.from_panel import panel as from_panel


class HoloViewsFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "holoviews"

    def register(self) -> None:
        import holoviews as hv  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        from marimo._output import formatting

        @formatting.formatter(hv.core.ViewableElement)
        @formatting.formatter(hv.core.Layout)
        @formatting.formatter(hv.HoloMap)
        @formatting.formatter(hv.DynamicMap)
        @formatting.formatter(hv.core.spaces.HoloMap)
        @formatting.formatter(hv.core.ndmapping.UniformNdMapping)
        @formatting.formatter(hv.core.ndmapping.NdMapping)
        def _show_chart(
            plot: (
                hv.core.ViewableElement
                | hv.core.Layout
                | hv.HoloMap
                | hv.DynamicMap
                | hv.core.spaces.HoloMap
                | hv.core.ndmapping.UniformNdMapping
                | hv.core.ndmapping.NdMapping
            ),
        ) -> tuple[KnownMimeType, str]:
            return from_panel(plot)._mime_()

    def apply_theme(self, theme: Theme) -> None:
        import holoviews as hv  # type: ignore

        if DependencyManager.bokeh.has():
            hv.renderer("bokeh").theme = (
                "dark_minimal" if theme == "dark" else None
            )
        if DependencyManager.plotly.has():
            hv.renderer("plotly").theme = (
                "plotly_dark" if theme == "dark" else "plotly"
            )
