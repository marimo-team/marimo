# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import build_stateless_plugin


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
            json_str = plotly.io.to_json(fig)
            plugin = Html(
                build_stateless_plugin(
                    component_name="marimo-plotly",
                    args={"figure": json.loads(json_str)},
                )
            )
            return ("text/html", plugin.text)
