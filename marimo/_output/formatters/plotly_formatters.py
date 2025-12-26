# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any

from marimo._config.config import Theme
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.notification_utils import CellNotificationUtils
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._runtime.context.utils import running_in_notebook


class PlotlyFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "plotly"

    def register(self) -> None:
        import plotly.graph_objects  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
        import plotly.io as pio  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        from marimo._output import formatting

        if running_in_notebook():

            def _show_plotly_figure(
                fig: plotly.graph_objects.Figure,
                config: dict[str, Any] | None = None,
            ) -> tuple[KnownMimeType, str]:
                dragmode = getattr(fig.layout, "dragmode", None)
                if dragmode is None:
                    # Users are accustomed to default zoom.
                    fig.update_layout(dragmode="zoom")
                json_str: str = pio.to_json(fig)
                plugin = PlotlyFormatter.render_plotly_dict(
                    json.loads(json_str), config=config
                )
                return ("text/html", plugin.text)

            @formatting.formatter(plotly.graph_objects.Figure)
            @formatting.formatter(plotly.graph_objects.FigureWidget)
            def _plotly_formatter(
                fig: plotly.graph_objects.Figure,
            ) -> tuple[KnownMimeType, str]:
                return _show_plotly_figure(fig)

            # Patch Figure.show to add to console output instead of opening a
            # browser.
            def patched_show(
                self: plotly.graph_objects.Figure,
                *args: Any,  # noqa: ARG001
                **kwargs: Any,
            ) -> None:
                # Extract config if provided
                config = kwargs.get("config")
                mimetype, data = _show_plotly_figure(self, config=config)
                CellNotificationUtils.broadcast_console_output(
                    channel=CellChannel.MEDIA,
                    mimetype=mimetype,
                    data=data,
                    cell_id=None,
                    status=None,
                )

            plotly.graph_objects.Figure.show = patched_show

    @staticmethod
    def render_plotly_dict(
        json: dict[Any, Any], config: dict[str, Any] | None = None
    ) -> Html:
        import plotly.io as pio  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        resolved_config: dict[str, Any] = {}

        # Ensure valid renderer for marimo environment
        if (
            not pio.renderers.default
            or pio.renderers.default not in pio.renderers
        ):
            pio.renderers.default = "browser"

        try:
            default_renderer: Any = pio.renderers[pio.renderers.default]
            resolved_config = default_renderer.config or {}
        except (AttributeError, KeyError):
            pass

        # Merge with any config passed via show()
        if config is not None:
            resolved_config = {**resolved_config, **config}

        return Html(
            build_stateless_plugin(
                component_name="marimo-plotly",
                args={"figure": json, "config": resolved_config},
            )
        )

    def apply_theme(self, theme: Theme) -> None:
        import plotly.io as pio  # type: ignore

        pio.templates.default = "plotly_dark" if theme == "dark" else "plotly"
