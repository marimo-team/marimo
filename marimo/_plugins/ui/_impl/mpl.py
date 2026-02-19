# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Final,
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


class MatplotlibSelection(Protocol):
    def get_mask(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.bool_]: ...


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
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array where `True` indicates the point is
            within the selection.
        """
        import numpy as np

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        return (
            (x_arr >= self.x_min)
            & (x_arr <= self.x_max)
            & (y_arr >= self.y_min)
            & (y_arr <= self.y_max)
        )


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
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array where `True` indicates the point is
            within the selection.
        """
        import numpy as np
        from matplotlib.path import Path  # type: ignore[import-untyped]

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        path = Path(self.vertices)
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
        """Return an all-``False`` mask.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array of all ``False``.
        """
        import numpy as np

        return np.zeros(len(np.asarray(x)), dtype=bool)

    def __bool__(self) -> bool:
        return False


def _figure_pixel_size(figure: Figure) -> tuple[float, float]:
    """Get figure dimensions in pixels."""
    dpi = figure.get_dpi()
    width_in, height_in = figure.get_size_inches()
    return width_in * dpi, height_in * dpi


def _figure_to_base64(figure: Figure) -> str:
    """Render a matplotlib figure to a base64-encoded PNG data URL."""
    buf = io.BytesIO()
    figure.savefig(buf, format="png")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return f"data:image/png;base64,{encoded}"


@mddoc
class matplotlib(UIElement[dict[str, JSONType], MatplotlibSelection]):
    """Make reactive selections on matplotlib plots.

    Use `mo.ui.matplotlib` to make matplotlib plots interactive: draw a box
    selection or a freehand lasso selection on the frontend, then use the
    selection geometry in Python to filter your data.

    The figure is rendered as a static image with an interactive selection
    overlay:

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
        value: The selected data, with `get_mask(x, y)` returning a
            mask array corresponding to the selection.

    Args:
        axes: A matplotlib `Axes` object. The full figure is rendered,
            but selections map to this axes' coordinate space.
        debounce: If `True`, the selection is only sent to Python on
            mouse-up. If `False` (the default), it streams while dragging.
    """

    name: Final[str] = "marimo-matplotlib"

    def __init__(self, axes: Axes, *, debounce: bool = False) -> None:
        DependencyManager.matplotlib.require("for `mo.ui.matplotlib`")

        from matplotlib.figure import Figure  # type: ignore[import-untyped]

        figure = axes.get_figure()
        if not isinstance(figure, Figure):
            raise ValueError("Axes must be attached to a figure.")
        self._ax: Axes = axes

        fig_width_px, fig_height_px = _figure_pixel_size(figure)

        # Axes pixel bounds: [left, top, right, bottom]
        # relative to the full figure image
        bbox = axes.get_position()
        axes_pixel_bounds: list[float] = [
            bbox.x0 * fig_width_px,  # left
            (1 - bbox.y1) * fig_height_px,  # top
            bbox.x1 * fig_width_px,  # right
            (1 - bbox.y0) * fig_height_px,  # bottom
        ]

        _SUPPORTED_SCALES = ("linear", "log")
        x_scale = axes.get_xscale()
        y_scale = axes.get_yscale()
        if x_scale not in _SUPPORTED_SCALES:
            raise ValueError(
                f"Unsupported x-axis scale {x_scale!r}. "
                f"mo.ui.matplotlib supports: {', '.join(_SUPPORTED_SCALES)}."
            )
        if y_scale not in _SUPPORTED_SCALES:
            raise ValueError(
                f"Unsupported y-axis scale {y_scale!r}. "
                f"mo.ui.matplotlib supports: {', '.join(_SUPPORTED_SCALES)}."
            )

        super().__init__(
            component_name=matplotlib.name,
            initial_value={},
            label="",
            args={
                "chart-base64": _figure_to_base64(figure),
                "x-bounds": list(axes.get_xlim()),
                "y-bounds": list(axes.get_ylim()),
                "axes-pixel-bounds": axes_pixel_bounds,
                "width": fig_width_px,
                "height": fig_height_px,
                "debounce": debounce,
                "x-scale": x_scale,
                "y-scale": y_scale,
            },
            on_change=None,
        )

    @property
    def axes(self) -> Axes:
        """The associated matplotlib Axes object."""
        return self._ax

    def _convert_value(
        self, value: dict[str, JSONType]
    ) -> MatplotlibSelection:
        if not value or not value.get("has_selection"):
            return EmptySelection()
        sel_type = value.get("type")
        data = value.get("data")

        if sel_type == "box":
            data = cast(dict[str, float], data)
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
