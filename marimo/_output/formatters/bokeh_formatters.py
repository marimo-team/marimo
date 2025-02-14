# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from marimo._config.config import Theme
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.utils import src_or_src_doc
from marimo._output.utils import flatten_string


class BokehFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "bokeh"

    def register(self) -> Callable[[], None]:
        import bokeh.models  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
        import bokeh.plotting  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        from marimo._output import formatting
        from marimo._runtime.output import _output

        old_show = bokeh.plotting.show
        # bokeh always starts with output_notebook() in Jupyter, but this
        # brings in a dependency on IPython, which we don't need.
        old_output_notebook = bokeh.plotting.output_notebook

        @functools.wraps(old_show)
        def show(*args: Any, **kwargs: Any) -> None:
            # Imperatively display the Bokeh object in the marimo output
            # area.
            if args:
                obj = args[0]
            else:
                obj = kwargs.get("obj", None)
            if obj is not None:
                _output.append(obj)

        @functools.wraps(old_output_notebook)
        def output_notebook(*args: Any, **kwargs: Any) -> None:
            # Noop
            del args
            del kwargs
            pass

        bokeh.plotting.show = show
        bokeh.plotting.output_notebook = output_notebook

        def unpatch() -> None:
            bokeh.plotting.show = old_show
            bokeh.plotting.output_notebook = old_output_notebook

        @formatting.formatter(bokeh.models.Plot)
        def _show_plot(
            plot: bokeh.models.Plot,
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

        return unpatch

    def apply_theme(self, theme: Theme) -> None:
        from bokeh.io import curdoc  # type: ignore

        curdoc().theme = "dark_minimal" if theme == "dark" else None  # type: ignore
