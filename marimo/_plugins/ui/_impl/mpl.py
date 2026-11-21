# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    cast,
)

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement

if TYPE_CHECKING:
    import numpy as np
    from matplotlib.axes import Axes  # type: ignore[import-untyped]
    from matplotlib.figure import Figure  # type: ignore[import-untyped]
    from numpy.typing import ArrayLike, NDArray

    from marimo._messaging.mimetypes import KnownMimeType


Dimension = bool | Literal["x", "y"]


class MatplotlibSelection(Protocol):
    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]: ...


def _panel_geometry(ax: Axes) -> dict[str, JSONType]:
    figure = ax.figure.canvas.figure
    bbox = ax.bbox.transformed(figure.transFigure.inverted())
    return {
        "rect": [bbox.x0, 1 - bbox.y1, bbox.x1, 1 - bbox.y0],
        "x": list(ax.get_xlim()),
        "y": list(ax.get_ylim()),
        "xScale": ax.get_xscale(),
        "yScale": ax.get_yscale(),
    }


def _to_numeric(arr: NDArray[Any]) -> NDArray[Any]:
    """Convert a numpy array to matplotlib's numeric representation.

    Only called on the slow path when a direct comparison raises
    `TypeError` (e.g. datetime vs float).  Uses
    `matplotlib.dates.date2num` which handles `datetime.datetime`,
    `datetime.date`, and `numpy.datetime64`.
    """
    from matplotlib.dates import date2num  # type: ignore[import-untyped]

    return date2num(arr)  # type: ignore[no-any-return,no-untyped-call]


@dataclass(frozen=True)
class BoxSelection:
    """A rectangular box selection on a matplotlib plot.

    Attributes:
        x_min: Left boundary of the selection.
        x_max: Right boundary of the selection.
        y_min: Bottom boundary of the selection.
        y_max: Top boundary of the selection.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]:
        """Get a boolean mask for points within this selection.

        Args:
            x: Array-like of x-coordinates (numeric or datetime).
            y: Array-like of y-coordinates (numeric or datetime).

        Returns:
            A boolean numpy array where `True` indicates the point is
            within the selection.
        """
        import numpy as np

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        try:
            return (
                (x_arr >= self.x_min)
                & (x_arr <= self.x_max)
                & (y_arr >= self.y_min)
                & (y_arr <= self.y_max)
            )
        except TypeError:
            x_arr = _to_numeric(x_arr)
            y_arr = _to_numeric(y_arr)
            return (
                (x_arr >= self.x_min)
                & (x_arr <= self.x_max)
                & (y_arr >= self.y_min)
                & (y_arr <= self.y_max)
            )


@dataclass(frozen=True)
class RangeSelection:
    axis: Literal["x", "y"]
    minimum: float
    maximum: float

    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]:
        import numpy as np

        values = np.asarray(x if self.axis == "x" else y)
        try:
            return (values >= self.minimum) & (values <= self.maximum)
        except TypeError:
            values = _to_numeric(values)
            return (values >= self.minimum) & (values <= self.maximum)


@dataclass(frozen=True)
class LassoSelection:
    """A freehand polygon (lasso) selection on a matplotlib plot.

    Attributes:
        vertices: The polygon vertices as a tuple of (x, y) pairs.
    """

    vertices: tuple[tuple[float, float], ...]

    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]:
        """Get a boolean mask for points within this selection.

        Args:
            x: Array-like of x-coordinates (numeric or datetime).
            y: Array-like of y-coordinates (numeric or datetime).

        Returns:
            A boolean numpy array where `True` indicates the point is
            within the selection.
        """
        import numpy as np
        from matplotlib.path import Path  # type: ignore[import-untyped]

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        path = Path(self.vertices)
        try:
            points = np.column_stack([x_arr, y_arr])
            return path.contains_points(points)
        except TypeError:
            x_arr = _to_numeric(x_arr)
            y_arr = _to_numeric(y_arr)
            points = np.column_stack([x_arr, y_arr])
            return path.contains_points(points)


@dataclass(frozen=True)
class EmptySelection:
    """Sentinel representing no selection.

    Returned by `mo.ui.matplotlib.value` when nothing is selected.

    Behaves like a selection with no points, and evaluates to False
    when coerced as a bool.
    """

    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]:  # noqa: ARG002
        """Return an all-`False` mask.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array of all `False`.
        """
        import numpy as np

        return np.zeros(len(np.asarray(x)), dtype=bool)

    def __bool__(self) -> bool:
        return False


def _figure_to_base64(figure: Figure) -> str:
    """Render a matplotlib figure to a base64-encoded PNG data URL."""
    # Keep the full figure in the snapshot so the brush can use figure coordinates.
    with io.BytesIO() as buf:
        figure.savefig(
            buf,
            format="png",
            dpi=2 * figure.get_dpi(),
            bbox_inches=figure.bbox_inches.frozen(),
        )
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


@mddoc
class matplotlib(UIElement[dict[str, JSONType], MatplotlibSelection]):
    """Make reactive selections on matplotlib plots.

    Use `mo.ui.matplotlib` to make matplotlib plots interactive: draw a box
    selection or a freehand lasso selection on the frontend, then use the
    selection geometry in Python to filter your data.

    The Matplotlib widget renders the figure. By default, you can:

    - click and drag for box selection;
    - hold the `Shift` key and drag for lasso selection.

    Example:
        ```python
        import matplotlib.pyplot as plt
        import marimo as mo
        import numpy as np

        x = np.arange(5)
        y = x**2
        plt.scatter(x=x, y=y)
        ax = mo.ui.matplotlib(plt.gca())
        ax
        ```

        ```python
        # Filter data using the selection
        mask = ax.value.get_mask(x, y)
        selected_x, selected_y = x[mask], y[mask]
        ```

        ```python
        # Check if anything is selected
        if ax.value:
            print("Data has been selected")
        ```

    Attributes:
        value: The current selection. Use `get_mask(x, y)` to find the selected points.

    Args:
        axes: The Matplotlib Axes to display.
        value: Initial box selection as `{"x": (min, max), "y": (min, max)}`.
            A one-dimensional brush needs only its selected dimension.
            The selection is clamped to the axes' bounds.
        brush: Enable selection in both dimensions (the default), disable it
            with `False`, or select a range with `"x"` or `"y"`.
        debounce: If `True`, the selection is only sent to Python on
            mouse-up. If `False` (the default), it streams while dragging.
    """

    def __init__(
        self,
        axes: Axes,
        value: dict[str, tuple[float, float]] | None = None,
        *,
        debounce: bool = False,
        brush: Dimension = True,
    ) -> None:
        DependencyManager.matplotlib.require("for `mo.ui.matplotlib`")

        from matplotlib.axes import Axes

        if not isinstance(axes, Axes):
            raise TypeError("Expected a Matplotlib Axes.")
        if axes.get_figure() is None:
            raise ValueError("Axes must be attached to a figure.")
        self._ax = axes
        figure = axes.figure.canvas.figure
        if not isinstance(brush, bool) and brush not in ("x", "y"):
            raise ValueError("brush must be True, False, 'x', or 'y'.")
        self._brush = brush

        for dim, scale in (("x", axes.get_xscale()), ("y", axes.get_yscale())):
            if scale not in ("linear", "log"):
                raise ValueError(
                    f"Unsupported {dim}-axis scale {scale!r}. "
                    "mo.ui.matplotlib supports: linear, log."
                )

        self._figure = figure
        initial_value: dict[str, JSONType] = {}
        if value is not None and brush is not False:
            x_bounds = axes.get_xlim()
            y_bounds = axes.get_ylim()
            try:
                selection_x_min, selection_x_max = sorted(
                    map(float, x_bounds if brush == "y" else value["x"])
                )
                selection_y_min, selection_y_max = sorted(
                    map(float, y_bounds if brush == "x" else value["y"])
                )
            except Exception:
                raise ValueError(
                    "`value` must be of the form {'x': (min, max), 'y': (min, max)}."
                ) from None
            axes_x_min, axes_x_max = sorted(x_bounds)
            axes_y_min, axes_y_max = sorted(y_bounds)
            x_min = max(selection_x_min, axes_x_min)
            x_max = min(selection_x_max, axes_x_max)
            y_min = max(selection_y_min, axes_y_min)
            y_max = min(selection_y_max, axes_y_max)
            if x_min <= x_max and y_min <= y_max:
                initial_value = {
                    "type": "box",
                    "has_selection": True,
                    "data": {
                        "x_min": x_min,
                        "x_max": x_max,
                        "y_min": y_min,
                        "y_max": y_max,
                    },
                }

        from marimo._output.hypertext import is_non_interactive
        from marimo._runtime.context import safe_get_context
        from marimo._runtime.context.kernel_context import KernelRuntimeContext

        ctx = safe_get_context()
        self._plot_widget = None
        if not is_non_interactive() and (
            not isinstance(ctx, KernelRuntimeContext)
            or ctx.virtual_files_supported
        ):
            try:
                from marimo._plugins.ui._impl.mpl_widget import (
                    _CloseView,
                    _PlotWidget,
                )
            except ModuleNotFoundError as exc:
                if exc.name not in {
                    "matplotlib.backends.backend_anywidget",
                    "jupyter_rfb",
                    "anywidget",
                    "ipywidgets",
                    "traitlets",
                }:
                    raise
                raise ImportError(
                    "Live plots require a Matplotlib version with the anywidget "
                    "backend. Install its widget extra with "
                    "pip install 'matplotlib[widget]'."
                ) from exc
            self._plot_widget = _PlotWidget(
                axes,
                selection=initial_value,
                brush=brush,
                debounce=debounce,
            )
            if isinstance(ctx, KernelRuntimeContext):
                ctx.cell_lifecycle_registry.add(_CloseView(self._plot_widget))
        model_id = (
            self._plot_widget.model_id if self._plot_widget is not None else ""
        )
        super().__init__(
            component_name="marimo-anywidget",
            initial_value=initial_value,
            label="",
            args={"model-id": model_id},
            on_change=None,
        )
        if self._plot_widget is not None:
            from marimo._plugins.ui._impl.comm import MarimoComm

            if isinstance(self._plot_widget.comm, MarimoComm):
                self._plot_widget.comm.ui_element_id = self._id

    def _frontend_initial_value(
        self, value: dict[str, JSONType]
    ) -> dict[str, JSONType]:
        del value
        return {
            "model_id": self._plot_widget.model_id if self._plot_widget else ""
        }

    @property
    def text(self) -> str:
        if self._plot_widget is None:
            return f'<img alt="Matplotlib figure" src="{_figure_to_base64(self._figure)}">'
        return super().text

    def _mime_(self) -> tuple[KnownMimeType, str]:
        if self._plot_widget is None:
            return ("image/png", _figure_to_base64(self._figure))
        return super()._mime_()

    @property
    def axes(self) -> Axes:
        """The Matplotlib object passed to the constructor."""
        return self._ax

    def _convert_value(
        self, value: dict[str, JSONType]
    ) -> MatplotlibSelection:
        if "selection" in value:
            value = cast(dict[str, JSONType], value["selection"])
        if not self._brush or not value or not value.get("has_selection"):
            return EmptySelection()
        sel_type = value.get("type")
        data = value.get("data")

        if sel_type == "box":
            data = cast(dict[str, float], data)
            if isinstance(self._brush, str):
                axis = self._brush
                return RangeSelection(
                    axis,
                    float(data[f"{axis}_min"]),
                    float(data[f"{axis}_max"]),
                )
            return BoxSelection(
                x_min=float(data["x_min"]),
                x_max=float(data["x_max"]),
                y_min=float(data["y_min"]),
                y_max=float(data["y_max"]),
            )
        if sel_type == "lasso":
            data = cast(list[list[float]], data)
            return LassoSelection(
                vertices=tuple((float(v[0]), float(v[1])) for v in data),
            )
        return EmptySelection()
