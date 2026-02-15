# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Optional,
    Union,
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


@dataclass(frozen=True)
class BoxSelection:
    """A rectangular box selection on a matplotlib chart.

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

    def contains_point(self, x: float, y: float) -> bool:
        """Test if a point is inside this selection.

        Args:
            x: The x-coordinate to test.
            y: The y-coordinate to test.

        Returns:
            ``True`` if the point is inside the box.
        """
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

    def get_mask(self, x: Any, y: Any) -> np.ndarray:
        """Get a boolean mask for points within this selection.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array where ``True`` indicates the point is
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

    def get_indices(self, x: Any, y: Any) -> np.ndarray:
        """Get the integer indices of points within this selection.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            An integer numpy array of indices that fall within the selection.
        """
        import numpy as np

        return np.where(self.get_mask(x, y))[0]


@dataclass(frozen=True)
class LassoSelection:
    """A freehand polygon (lasso) selection on a matplotlib chart.

    Attributes:
        vertices: The polygon vertices as a tuple of (x, y) pairs.
    """

    vertices: tuple[tuple[float, float], ...]

    def contains_point(self, x: float, y: float) -> bool:
        """Test if a point is inside this selection.

        Args:
            x: The x-coordinate to test.
            y: The y-coordinate to test.

        Returns:
            ``True`` if the point is inside the lasso polygon.
        """
        from matplotlib.path import Path  # type: ignore[import-untyped]

        path = Path(self.vertices)
        return bool(path.contains_point((x, y)))

    def get_mask(self, x: Any, y: Any) -> np.ndarray:
        """Get a boolean mask for points within this selection.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array where ``True`` indicates the point is
            within the selection.
        """
        import numpy as np
        from matplotlib.path import Path  # type: ignore[import-untyped]

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        path = Path(self.vertices)
        points = np.column_stack([x_arr, y_arr])
        return path.contains_points(points)

    def get_indices(self, x: Any, y: Any) -> np.ndarray:
        """Get the integer indices of points within this selection.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            An integer numpy array of indices that fall within the selection.
        """
        import numpy as np

        return np.where(self.get_mask(x, y))[0]


MatplotlibSelection = Optional[Union[BoxSelection, LassoSelection]]


@mddoc
class matplotlib(UIElement[dict[str, JSONType], MatplotlibSelection]):
    """Make reactive selections on matplotlib charts.

    Use `mo.ui.matplotlib` to make matplotlib plots interactive: draw a box
    selection or a freehand lasso selection on the frontend, then use the
    selection geometry in Python to filter your data.

    The figure is rendered as a static image with an interactive selection
    overlay. Click and drag for box selection; hold **Shift** and drag for
    lasso (freehand polygon) selection.

    Examples:
        ```python
        import matplotlib.pyplot as plt
        import marimo as mo

        fig, ax = plt.subplots()
        ax.scatter([1, 2, 3, 4, 5], [2, 4, 1, 5, 3])
        chart = mo.ui.matplotlib(ax)
        ```

        ```python
        # View the chart and selection data
        mo.hstack([chart, chart.value])
        ```

        ```python
        # Filter data using the selection
        import numpy as np

        x = np.array([1, 2, 3, 4, 5])
        y = np.array([2, 4, 1, 5, 3])
        mask = chart.get_mask(x, y)
        selected_x, selected_y = x[mask], y[mask]
        ```

    Attributes:
        value: ``None`` when nothing is selected. A ``BoxSelection`` for
            box selections or a ``LassoSelection`` for lasso selections.
        selection: Convenience alias for ``value``.

    Args:
        ax: A matplotlib ``Axes`` object. The full figure is rendered,
            but selections map to this axes' coordinate space.
        debounce: If ``True``, the selection is only sent to Python on
            mouse-up. If ``False`` (the default), it streams while dragging.
        label: Markdown label for the element. Defaults to ``""``.
        on_change: Optional callback invoked when the selection changes.
    """

    name: Final[str] = "marimo-matplotlib"

    def __init__(
        self,
        ax: Axes,
        *,
        debounce: bool = False,
        label: str = "",
        on_change: Optional[Callable[[MatplotlibSelection], None]] = None,
    ) -> None:
        DependencyManager.matplotlib.require("for `mo.ui.matplotlib`")

        from matplotlib.figure import Figure  # type: ignore[import-untyped]

        figure = ax.get_figure()
        if not isinstance(figure, Figure):
            raise ValueError("Axes must be attached to a figure.")

        # Data-space bounds
        x_bounds: list[float] = list(ax.get_xlim())
        y_bounds: list[float] = list(ax.get_ylim())

        # Axes pixel bounds: [left, top, right, bottom]
        # relative to the full figure image
        fig_width_px, fig_height_px = _figure_pixel_size(figure)
        bbox = ax.get_position()
        axes_pixel_bounds: list[float] = [
            bbox.x0 * fig_width_px,  # left
            (1 - bbox.y1) * fig_height_px,  # top
            bbox.x1 * fig_width_px,  # right
            (1 - bbox.y0) * fig_height_px,  # bottom
        ]

        # Render figure to base64 PNG
        chart_base64 = _figure_to_base64(figure)

        super().__init__(
            component_name=matplotlib.name,
            initial_value={},
            label=label,
            args={
                "chart-base64": chart_base64,
                "x-bounds": x_bounds,
                "y-bounds": y_bounds,
                "axes-pixel-bounds": axes_pixel_bounds,
                "width": fig_width_px,
                "height": fig_height_px,
                "debounce": debounce,
            },
            on_change=on_change,
        )

    def _convert_value(
        self, value: dict[str, JSONType]
    ) -> MatplotlibSelection:
        if not value or not value.get("has_selection"):
            return None
        sel_type = value.get("type")
        data = value.get("data")

        if sel_type == "box":
            data = cast(dict, data)
            return BoxSelection(
                x_min=float(data["x_min"]),
                x_max=float(data["x_max"]),
                y_min=float(data["y_min"]),
                y_max=float(data["y_max"]),
            )
        if sel_type == "lasso":
            data = cast(list, data)
            return LassoSelection(
                vertices=tuple((float(v[0]), float(v[1])) for v in data),
            )
        return None

    @property
    def selection(self) -> MatplotlibSelection:
        """The current selection, or None if nothing is selected."""
        return self.value

    def get_vertices(self) -> list[tuple[float, float]]:
        """Get the vertices of the current selection.

        Returns:
            For box selections, the 4 corners of the rectangle.
            For lasso selections, the list of polygon vertices.
            Returns an empty list if nothing is selected.
        """
        v = self.value
        if v is None:
            return []
        if isinstance(v, BoxSelection):
            return [
                (v.x_min, v.y_min),
                (v.x_max, v.y_min),
                (v.x_max, v.y_max),
                (v.x_min, v.y_max),
            ]
        # lasso
        return list(v.vertices)

    def contains_point(self, x: float, y: float) -> bool:
        """Test if a point is inside the current selection.

        Args:
            x: The x-coordinate to test.
            y: The y-coordinate to test.

        Returns:
            ``True`` if the point is inside the selection, ``False`` otherwise
            or if nothing is selected.
        """
        if self.value is None:
            return False
        return self.value.contains_point(x, y)

    def get_mask(
        self,
        x: Any,
        y: Any,
    ) -> np.ndarray:
        """Get a boolean mask for points within the selection.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            A boolean numpy array where ``True`` indicates the point is
            within the selection. Returns all-``False`` if nothing is selected.
        """
        import numpy as np

        if self.value is None:
            return np.zeros(len(np.asarray(x)), dtype=bool)
        return self.value.get_mask(x, y)

    def get_indices(
        self,
        x: Any,
        y: Any,
    ) -> np.ndarray:
        """Get the integer indices of points within the selection.

        Args:
            x: Array-like of x-coordinates.
            y: Array-like of y-coordinates.

        Returns:
            An integer numpy array of indices that fall within the
            selection. Returns an empty array if nothing is selected.
        """
        import numpy as np

        if self.value is None:
            return np.arange(0)
        return self.value.get_indices(x, y)


def _figure_pixel_size(
    figure: Figure,
) -> tuple[Union[int, float], Union[int, float]]:
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
