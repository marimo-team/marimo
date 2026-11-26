# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    Protocol,
    TypeVar,
    cast,
    overload,
)

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy as np
    from matplotlib.axes import Axes  # type: ignore[import-untyped]
    from matplotlib.figure import Figure, SubFigure  # type: ignore[import-untyped]
    from numpy.typing import ArrayLike, NDArray

    from marimo._messaging.mimetypes import KnownMimeType


Dimension = bool | Literal["x", "y"]


class MatplotlibSelection(Protocol):
    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]: ...


class AxesSelections(Mapping["Axes", MatplotlibSelection]):
    """Selections in figure order. Look up a panel by Axes, position, or unique label."""

    def __init__(self, selections: dict[Axes, MatplotlibSelection]) -> None:
        self._selections = selections.copy()
        self._axes = tuple(selections)

    def __len__(self) -> int:
        return len(self._axes)

    def __iter__(self) -> Iterator[Axes]:
        return iter(self._axes)

    def __getitem__(self, key: Axes | int | str) -> MatplotlibSelection:
        if isinstance(key, int):
            key = self._axes[key]
        elif isinstance(key, str):
            matches = [
                ax for ax in self._axes if key and ax.get_label() == key
            ]
            if not matches:
                raise KeyError(key)
            if len(matches) > 1:
                raise KeyError(
                    f"Multiple Axes have label {key!r}; use a position or Axes object."
                )
            key = matches[0]
        return self._selections[key]


_Target = TypeVar("_Target", bound="Axes | Figure | SubFigure")
_Container = TypeVar("_Container", bound="Figure | SubFigure")
_Value = TypeVar("_Value", bound="MatplotlibSelection | AxesSelections")


def _subfigure_axes(subfigure: SubFigure) -> Iterator[Axes]:
    yield from subfigure.axes
    for child in subfigure.subfigs:
        yield from _subfigure_axes(child)


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
class matplotlib(
    UIElement[dict[str, JSONType], _Value], Generic[_Target, _Value]
):
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
        value: A selection for one Axes, or an `AxesSelections` collection
            for a Figure or SubFigure. Each selection has `get_mask(x, y)`.

    Args:
        axes: An `Axes`, `Figure`, or `SubFigure`. A single Axes returns a
            selection. For containers, index `.value` by subplot position,
            unique Axes label, or Axes object. Subfigures scope selection and
            navigation to their own panels in the rendered figure.
        value: Initial box selection as `{"x": (min, max), "y": (min, max)}`.
            A one-dimensional brush needs only its selected dimension.
            The selection is clamped to the axes' bounds.
        brush: Enable selection in both dimensions (the default), disable it
            with `False`, or select a range with `"x"` or `"y"`.
        pan: Enable drag-to-pan in both dimensions, or only `"x"` or `"y"`.
            With `pan="x"`, a horizontal trackpad swipe also pans the plot.
        zoom: Enable wheel zoom in both dimensions, or only `"x"` or `"y"`.
            Pan and zoom use the anywidget Matplotlib backend in a live notebook.
        debounce: If `True`, the selection is only sent to Python on
            mouse-up. If `False` (the default), it streams while dragging.
    """

    @overload
    def __init__(
        self: matplotlib[Axes, MatplotlibSelection],
        axes: Axes,
        value: dict[str, tuple[float, float]] | None = None,
        *,
        debounce: bool = False,
        brush: Dimension = True,
        pan: Dimension = False,
        zoom: Dimension = False,
    ) -> None: ...

    @overload
    def __init__(
        self: matplotlib[_Container, AxesSelections],
        axes: _Container,
        value: None = None,
        *,
        debounce: bool = False,
        brush: Dimension = True,
        pan: Dimension = False,
        zoom: Dimension = False,
    ) -> None: ...

    def __init__(
        self,
        axes: Axes | Figure | SubFigure,
        value: dict[str, tuple[float, float]] | None = None,
        *,
        debounce: bool = False,
        brush: Dimension = True,
        pan: Dimension = False,
        zoom: Dimension = False,
    ) -> None:
        DependencyManager.matplotlib.require("for `mo.ui.matplotlib`")

        from matplotlib.axes import Axes
        from matplotlib.figure import Figure, SubFigure  # type: ignore[import-untyped]

        self._target = cast(_Target, axes)
        panels: tuple[Axes, ...]
        self._single = isinstance(axes, Axes)
        if isinstance(axes, Axes):
            panels = (axes,)
            if axes.get_figure() is None:
                raise ValueError("Axes must be attached to a figure.")
            figure = axes.figure.canvas.figure
        elif isinstance(axes, Figure):
            figure = axes
            panels = tuple(axes.axes)
        elif isinstance(axes, SubFigure):
            figure = axes.canvas.figure
            scoped = set(_subfigure_axes(axes))
            panels = tuple(ax for ax in figure.axes if ax in scoped)
        else:
            raise TypeError(
                "Expected a Matplotlib Axes, Figure, or SubFigure."
            )
        self._panels = panels
        if not self._single and value is not None:
            raise ValueError(
                "An initial box selection requires a single Axes."
            )
        for name, option in (("brush", brush), ("pan", pan), ("zoom", zoom)):
            if not isinstance(option, bool) and option not in ("x", "y"):
                raise ValueError(f"{name} must be True, False, 'x', or 'y'.")
        self._brush = brush

        for ax in panels:
            for dim, scale in (("x", ax.get_xscale()), ("y", ax.get_yscale())):
                if scale not in ("linear", "log"):
                    raise ValueError(
                        f"Unsupported {dim}-axis scale {scale!r}. "
                        "mo.ui.matplotlib supports: linear, log."
                    )

        self._figure = figure
        initial_value: dict[str, JSONType] = {}
        if value is not None and brush is not False:
            x_bounds = panels[0].get_xlim()
            y_bounds = panels[0].get_ylim()
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
        if not self._single:
            initial_value = {"panels": {}}

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
                figure,
                panels,
                selection=initial_value,
                single=self._single,
                brush=brush,
                pan=pan,
                zoom=zoom,
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
    def axes(self) -> _Target:
        """The Matplotlib object passed to the constructor."""
        return self._target

    def _convert_value(self, value: dict[str, JSONType]) -> _Value:
        if "selection" in value:
            value = cast(dict[str, JSONType], value["selection"])
        if self._single:
            return cast(_Value, self._selection(value))
        by_panel = cast(
            dict[str, dict[str, JSONType]], value.get("panels") or {}
        )
        return cast(
            _Value,
            AxesSelections(
                {
                    ax: self._selection(by_panel.get(str(index), {}))
                    for index, ax in enumerate(self._panels)
                }
            ),
        )

    def _selection(self, value: dict[str, JSONType]) -> MatplotlibSelection:
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
