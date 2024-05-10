# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.utils import src_or_src_doc
from marimo._output.utils import flatten_string


class BokehFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "bokeh"

    def register(self) -> None:
        import bokeh.models  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        from marimo._output import formatting

        @formatting.formatter(bokeh.models.Model)
        def _show_plot(
            plot: bokeh.models.Model,
        ) -> tuple[KnownMimeType, str]:
            import bokeh.embed  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
            import bokeh.resources  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
            from bokeh.io import (  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
                curdoc,
            )

            current_theme = curdoc().theme
            html_content = bokeh.embed.file_html(
                plot, bokeh.resources.CDN, theme=current_theme
            )
            return (
                "text/html",
                flatten_string(
                    h.iframe(
                        **src_or_src_doc(html_content),
                        onload="__resizeIframe(this)",
                        style="width: 100%",
                    )
                ),
            )
