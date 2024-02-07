# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import marimo._output.data.data as mo_data
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
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

            html = bokeh.embed.file_html(plot, bokeh.resources.CDN)
            html_file = mo_data.html(html)
            return (
                "text/html",
                (
                    flatten_string(
                        f"<iframe src='{html_file.url}'"
                        "frameborder='0' scrolling='auto'"
                        "style='width: 100%'"
                        "onload='__resizeIframe(this)'></iframe>"
                    )
                ),
            )
