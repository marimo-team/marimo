# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    from numpy.typing import NDArray

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


class _NavigationWidget(_FigureWidget):
    geometry = traitlets.Dict().tag(sync=True)

    def __init__(
        self,
        ax: Axes,
        *,
        pan: Dimension,
        zoom: Dimension,
    ) -> None:
        canvas = ax.figure.canvas
        if not isinstance(canvas, FigureCanvas):
            canvas = FigureCanvas(canvas.figure)
        self._navigation_size: tuple[int, int] | None = None
        # jupyter_rfb displays an empty ipywidgets.Output during construction.
        # The composed plot owns the cell output.
        with hide_ipython_display(Output):
            super().__init__(canvas)
        self.ax = ax
        self.directions = {"pan": pan, "zoom": zoom}
        self.home = ax.get_xlim(), ax.get_ylim()
        self.resizable = False
        self.on_msg(self._navigate)
        self.canvas.mpl_connect("draw_event", self._geometry)
        self.canvas.draw()

    def get_frame(self) -> NDArray[Any]:
        # Tick labels can change width at every wheel step. Keep the subplot
        # margins for this frame so the data under the pointer stays put.
        size, self._navigation_size = self._navigation_size, None
        figure = self.canvas.figure
        engine = figure.get_layout_engine()
        if engine is None or size != self.canvas.get_width_height(
            physical=True
        ):
            return super().get_frame()
        figure.set_layout_engine("none")
        try:
            return super().get_frame()
        finally:
            figure.set_layout_engine(engine)

    def _geometry(self, event: DrawEvent) -> None:
        if event.canvas is not self.canvas or self.canvas.is_saving():
            return
        self.geometry = _panel_geometry(self.ax)

    def _navigate(
        self, _widget: Any, message: dict[str, Any], _buffers: Any
    ) -> None:
        gestures = message.get("gestures", [message])
        if isinstance(gestures, list):
            for gesture in gestures:
                if isinstance(gesture, dict):
                    self._apply_gesture(gesture)

    def _apply_gesture(self, message: dict[str, Any]) -> None:
        action = message.get("navigation")
        if action == "reset":
            xlim, ylim = self.home
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)
        elif action in ("pan", "zoom"):
            if not all(
                isinstance(message.get(key), (int, float))
                and isfinite(message[key])
                for key in ("x", "y")
            ):
                return
            factor = message.get("factor", 1)
            if action == "zoom" and (
                not isinstance(factor, (int, float))
                or not isfinite(factor)
                or factor <= 0
            ):
                return
            ax = self.ax
            enabled = self.directions[action]
            for dim, axis, get_lim, set_lim in (
                ("x", ax.xaxis, ax.get_xlim, ax.set_xlim),
                ("y", ax.yaxis, ax.get_ylim, ax.set_ylim),
            ):
                if enabled is not True and enabled != dim:
                    continue
                fraction = float(message[dim])
                if action == "pan" and fraction == 0:
                    # Setting an unchanged limit would disable autoscaling.
                    continue
                transform = axis.get_transform()
                limits = transform.transform(get_lim())
                span = limits[1] - limits[0]
                if action == "pan":
                    limits = limits - span * fraction
                else:
                    anchor = limits[0] + span * fraction
                    limits = anchor + (limits - anchor) * factor
                result = transform.inverted().transform(limits)
                if all(map(isfinite, result)) and result[0] != result[1]:
                    set_lim(result)
        else:
            return
        # Agg draws synchronously in draw_idle(). Let the framebuffer combine
        # gestures and render the latest limits when the browser is ready.
        self._navigation_size = self.canvas.get_width_height(physical=True)
        self.request_draw()


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
    .marimo-mpl-controls {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 2px;
    }
    .marimo-mpl-controls button {
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        padding: 0;
        border: 0;
        border-radius: 4px;
        background: transparent;
        color: var(--muted-foreground, GrayText);
        cursor: pointer;
    }
    .marimo-mpl-controls button:hover {
        background: var(--muted, ButtonFace);
    }
    .marimo-mpl-controls button[aria-pressed="true"] {
        color: var(--blue-11, Highlight);
        background: var(--accent, ButtonFace);
        box-shadow: inset 0 0 0 1px currentColor;
    }
    .marimo-mpl-controls button:focus-visible {
        outline: 2px solid var(--ring, Highlight);
        outline-offset: 1px;
    }
    .marimo-mpl-controls [role="separator"] {
        height: 16px;
        margin-inline: 3px;
        border-inline-start: 1px solid var(--border, GrayText);
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
        self.figure_widget = _NavigationWidget(
            ax, pan=options["pan"], zoom=options["zoom"]
        )
        super().__init__(
            figure_ref=f"anywidget:{self.figure_widget.model_id}",
            selection=selection,
            options=options,
        )

    def close(self) -> None:
        self.figure_widget.close()
        super().close()
