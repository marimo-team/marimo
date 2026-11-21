# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import anywidget  # noqa: TID253 (loaded only for live Matplotlib plots)
import traitlets
from ipywidgets import Output
from matplotlib.backends.backend_anywidget import FigureCanvas, _FigureWidget

from marimo._output.formatters.ipython_formatters import hide_ipython_display
from marimo._plugins.ui._impl.mpl import _panel_geometry
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.backend_bases import DrawEvent

    from marimo._plugins.core.web_component import JSONType
    from marimo._plugins.ui._impl.mpl import Dimension
    from marimo._runtime.context import RuntimeContext


class _CloseView(CellLifecycleItem):
    def __init__(self, widget: _PlotWidget) -> None:
        self.widget = widget

    def create(self, context: RuntimeContext) -> None:
        del context

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
        del context, deletion
        self.widget.close()
        return True


class _AxesWidget(_FigureWidget):
    geometry = traitlets.Dict().tag(sync=True)

    def __init__(self, ax: Axes) -> None:
        canvas = ax.figure.canvas
        if not isinstance(canvas, FigureCanvas):
            canvas = FigureCanvas(canvas.figure)
        # jupyter_rfb displays an empty ipywidgets.Output during construction.
        # The composed plot owns the cell output.
        with hide_ipython_display(Output):
            super().__init__(canvas)
        self.ax = ax
        self.resizable = False
        self.canvas.mpl_connect("draw_event", self._geometry)
        self.canvas.draw()

    def _geometry(self, event: DrawEvent) -> None:
        if event.canvas is not self.canvas or self.canvas.is_saving():
            return
        self.geometry = _panel_geometry(self.ax)


class _PlotWidget(anywidget.AnyWidget):
    _esm = Path(__file__).with_suffix(".js")

    _css = """
    .marimo-mpl-figure .renderview-wrapper .renderview-view {
        border: 0;
        border-radius: 0;
    }
    .marimo-mpl-figure .renderview-wrapper { max-width: 100%; }
    /* jupyter_rfb stretches this gray pixel to the plot size before its first frame. */
    .marimo-mpl-figure img[src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mOor68HAAL+AX6E2KOJAAAAAElFTkSuQmCC"] {
        opacity: 0;
    }
    """
    figure_ref = traitlets.Unicode().tag(sync=True)
    selection = traitlets.Dict().tag(sync=True)
    options = traitlets.Dict().tag(sync=True)

    def __init__(
        self,
        ax: Axes,
        *,
        selection: dict[str, JSONType],
        **options: Dimension,
    ) -> None:
        self.figure_widget = _AxesWidget(ax)
        super().__init__(
            figure_ref=f"anywidget:{self.figure_widget.model_id}",
            selection=selection,
            options=options,
        )

    def close(self) -> None:
        self.figure_widget.close()
        super().close()
