# Copyright 2026 Marimo. All rights reserved.
"""
Interactive matplotlib plots, based on WebAgg.

Adapted from https://matplotlib.org/stable/gallery/user_interfaces/embedding_webagg_sgskip.html
"""

from __future__ import annotations

import io
import warnings
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._runtime.context import (
    get_context,
)
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._utils.data_uri import build_data_url

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure, SubFigure


def new_figure_manager_given_figure(
    num: int, figure: Figure | SubFigure | Axes
) -> Any:
    from matplotlib.backends.backend_webagg_core import (
        FigureCanvasWebAggCore,
        FigureManagerWebAgg as CoreFigureManagerWebAgg,
        NavigationToolbar2WebAgg as CoreNavigationToolbar2WebAgg,
    )

    class FigureManagerWebAgg(CoreFigureManagerWebAgg):
        _toolbar2_class = CoreNavigationToolbar2WebAgg  # type: ignore[assignment]

    class FigureCanvasWebAgg(FigureCanvasWebAggCore):
        manager_class = FigureManagerWebAgg  # type: ignore[assignment]

    # Suppress the "Starting a Matplotlib GUI outside of the main thread"
    # warning.  WebAgg only renders to an in-memory Agg buffer and
    # communicates over the network — no actual GUI toolkit is involved,
    # so the warning is a false positive (especially in marimo-run mode
    # where the kernel runs on a worker thread).
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Starting a Matplotlib GUI outside of the main thread",
            category=UserWarning,
        )
        canvas = FigureCanvasWebAgg(figure)  # type: ignore[no-untyped-call]
        manager = FigureManagerWebAgg(canvas, num)  # type: ignore[no-untyped-call]
    return manager


def png_bytes(figure: Figure | SubFigure | Axes) -> bytes:
    """Convert a matplotlib figure to base64-encoded PNG bytes.

    The Html._mime_ method expects _repr_png_ to return bytes that
    can be decoded to a UTF-8 string, so we return base64-encoded data.
    """
    import base64

    from matplotlib.figure import Figure

    buf = io.BytesIO()
    if isinstance(figure, Figure):
        figure.savefig(buf, format="png", bbox_inches="tight")
    else:
        figure.figure.canvas.print_figure(buf, format="png")
    return base64.b64encode(buf.getvalue())


class NonInteractiveMplHtml(Html):
    def __init__(self, figure: Figure | SubFigure | Axes) -> None:
        self._figure = figure
        super().__init__(as_html(figure).text)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        data_url = build_data_url(
            mimetype="image/png", data=png_bytes(self._figure)
        )
        return ("image/png", data_url)


@mddoc
def interactive(figure: Figure | SubFigure | Axes) -> Html:
    """Render a matplotlib figure using an interactive viewer.

    The interactive viewer allows you to pan, zoom, and see plot coordinates
    on mouse hover.

    Example:
        ```python
        plt.plot([1, 2])
        # plt.gcf() gets the current figure
        mo.mpl.interactive(plt.gcf())
        ```

    Args:
        figure (matplotlib Figure or Axes): A matplotlib `Figure` or `Axes` object.

    Returns:
        Html: An interactive matplotlib figure as an `Html` object.
    """
    # No top-level imports of matplotlib, since it isn't a required
    # dependency
    from matplotlib.axes import Axes

    if isinstance(figure, Axes):
        maybe_figure = figure.get_figure()
        assert maybe_figure is not None, "Axes object does not have a Figure"
        figure = maybe_figure

    ctx = get_context()
    if not isinstance(ctx, KernelRuntimeContext):
        return NonInteractiveMplHtml(figure)

    # When virtual files are not supported (e.g., during HTML export),
    # fall back to static PNG instead of interactive plot
    if not ctx.virtual_files_supported:
        return NonInteractiveMplHtml(figure)

    # Figure::figure returns self; SubFigure::figure returns the parent Figure
    is_subfigure = figure.figure is not figure
    if is_subfigure:
        warnings.warn(
            message="SubFigure is not supported in interactive mode; "
            "rendering as static PNG instead. "
            "Consider using a regular Figure instead.",
            stacklevel=2,
        )
        return NonInteractiveMplHtml(figure=figure)

    from marimo._plugins.ui._impl.from_mpl_interactive import mpl_interactive

    return mpl_interactive(figure)


# Custom CSS to make the mpl toolbar fit the marimo UI
css_content = """
.ui-dialog-titlebar + div {
    border-radius: 4px;
}
.ui-dialog-titlebar {
    display: none;
}
.mpl-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
}
select.mpl-widget,
.mpl-button-group {
    margin: 4px 0;
    border-radius: 6px;
    box-shadow: rgba(0, 0, 0, 0) 0px 0px 0px 0px,
        rgba(0, 0, 0, 0) 0px 0px 0px 0px,
        rgba(15, 23, 42, 0.1) 1px 1px 0px 0px,
        rgba(15, 23, 42, 0.1) 0px 0px 2px 0px;
}
.mpl-button-group + .mpl-button-group {
    margin-left: 0;
}
.mpl-button-group > .mpl-widget {
    padding: 4px;
}
.mpl-button-group > .mpl-widget > img {
    height: 16px;
    width: 16px;
}
.mpl-widget:disabled, .mpl-widget[disabled]
.mpl-widget:disabled, .mpl-widget[disabled]:hover {
    opacity: 0.5;
    background-color: #fff;
    border-color: #ccc !important;
}
.mpl-message {
    color: rgb(139, 141, 152);
    font-size: 11px;
}
.mpl-widget img {
    filter: invert(0.3);
}
""".strip()


def patch_javascript(javascript: str) -> str:
    # Comment out canvas.focus() and canvas_div.focus() calls
    # https://github.com/matplotlib/matplotlib/blob/4c345b42048811a2122ba0db68551c6ea4ddaf6a/lib/matplotlib/backends/web_backend/js/mpl.js#L338-L343
    javascript = javascript.replace(
        " canvas.focus();",
        "// canvas.focus(); // don't steal focus when in marimo",
    )
    javascript = javascript.replace(
        " canvas_div.focus();",
        "// canvas_div.focus(); // don't steal focus when in marimo",
    )
    return javascript
