# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import marimo._output.data.data as mo_data
from marimo._output.formatters.formatter_factory import FormatterFactory


class PlotlyFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "plotly"

    def register(self) -> None:
        import plotly.graph_objects  # type:ignore[import]
        import plotly.io  # type:ignore[import]

        from marimo._output import formatting

        @formatting.formatter(plotly.graph_objects.Figure)
        def _show_plotly_figure(
            fig: plotly.graph_objects.Figure,
        ) -> tuple[str, str]:
            # Outputting the HTML directly results in a memory leak; we use an
            # iframe to get around the leak. (See
            # https://github.com/marimo-team/marimo/issues/417)
            contents = plotly.io.to_html(fig)
            file = mo_data.html(contents)
            return (
                "text/html",
                (
                    f"<iframe src='{file.url}'"
                    "frameborder='0' scrolling='auto'"
                    "style='width: 100%; height: 450px'"
                    "onload='__resizeIframe(this)'></iframe>"
                ),
            )
