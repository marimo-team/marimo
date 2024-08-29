# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

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

            # Try to get the background fill color
            background_fill_color: Optional[str] = None
            try:
                attrs = current_theme._json.get("attrs", {})
                background_fill_color = attrs.get("BaseColorBar", {}).get(
                    "background_fill_color"
                ) or attrs.get("Plot", {}).get("background_fill_color")
            except Exception:
                pass

            # Maybe add <style> to the content
            if background_fill_color is not None:
                style_to_add = (
                    "<style>"
                    f"body{{background-color:{background_fill_color}}}"
                    "</style>"
                )
                # Add above the </head> tag
                html_content = html_content.replace(
                    "</head>", style_to_add + "</head>"
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
