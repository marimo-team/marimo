# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.plotly_formatters import PlotlyFormatter
from marimo._output.formatting import as_html


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
            backend_output = hv.render(plot)

            # If its a dict, then its a plotly figure,
            # and we should convert it to a plotly object
            if DependencyManager.plotly.has() and isinstance(
                backend_output, dict
            ):
                plotly_html = PlotlyFormatter.render_plotly_dict(
                    backend_output
                )
                return ("text/html", plotly_html.text)

            # Call as_html to recurse back into the formatter
            # this may be bokeh, matplotlib, or plotly
            html = as_html(backend_output)

            return ("text/html", html.text)
