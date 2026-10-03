# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import importlib
from typing import TYPE_CHECKING, Any

from marimo._config.config import Theme
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.formatters.utils import src_or_src_doc
from marimo._output.utils import flatten_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from bokeh.document import Document  # type: ignore[import-not-found,import-untyped,unused-ignore]
    from bokeh.model import Model  # type: ignore[import-not-found,import-untyped,unused-ignore]


def _show_plot(plot: Model | Document) -> tuple[KnownMimeType, str]:
    import bokeh.embed  # type: ignore[import-not-found,import-untyped,unused-ignore]
    import bokeh.resources  # type: ignore[import-not-found,import-untyped,unused-ignore]
    from bokeh.io import curdoc  # type: ignore[import-not-found,import-untyped,unused-ignore]

    current_theme = curdoc().theme
    html_content = bokeh.embed.file_html(
        plot, bokeh.resources.CDN, theme=current_theme
    )

    # Try to get the background fill color
    background_fill_color: str | None = None
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
            f"<style>body{{background-color:{background_fill_color}}}</style>"
        )
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


# Register on submodule completion: importing them from the root package's
# hook can deadlock against another thread importing a Bokeh submodule.
class BokehModelFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "bokeh.model"

    def register(self) -> None:
        from bokeh.model import Model  # type: ignore[import-not-found,import-untyped,unused-ignore]

        from marimo._output import formatting

        formatting.formatter(Model)(_show_plot)


class BokehDocumentFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "bokeh.document"

    def register(self) -> None:
        from bokeh.document import Document  # type: ignore[import-not-found,import-untyped,unused-ignore]

        from marimo._output import formatting

        formatting.formatter(Document)(_show_plot)


class BokehIOFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "bokeh.io"

    def register(self) -> Callable[[], None]:
        from marimo._runtime.output import _output

        # The import hook runs before Python binds the module on its parent.
        module = importlib.import_module(self.package_name())
        old_show = module.show
        # bokeh always starts with output_notebook() in Jupyter, but this
        # brings in a dependency on IPython, which we don't need.
        old_output_notebook = module.output_notebook

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

        module.__dict__.update(show=show, output_notebook=output_notebook)

        def unpatch() -> None:
            module.__dict__.update(
                show=old_show, output_notebook=old_output_notebook
            )

        return unpatch

    def apply_theme(self, theme: Theme) -> None:
        from bokeh.io import curdoc  # type: ignore

        curdoc().theme = "dark_minimal" if theme == "dark" else None  # type: ignore


class BokehPlottingFormatter(BokehIOFormatter):
    @staticmethod
    def package_name() -> str:
        return "bokeh.plotting"
