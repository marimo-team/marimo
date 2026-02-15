# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Optional,
    Union,
)

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement

if TYPE_CHECKING:
    import numpy as np
    from matplotlib.figure import Figure  # type: ignore[import-untyped]

# The selection bounds sent back to Python, or None when nothing is selected.
# When selected: {"x_min": float, "x_max": float, "y_min": float, "y_max": float}
MatplotlibSelection = Optional[dict[str, Any]]


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
        chart = mo.ui.matplotlib(fig)
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
        value: ``None`` when nothing is selected. When a box is selected:
            ``{"type": "box", "data": {"x_min": ..., "x_max": ...,
            "y_min": ..., "y_max": ...}}``.
            When a lasso is selected:
            ``{"type": "lasso", "data": [(x, y), ...]}``.
            Use helper methods like ``get_mask()`` for type-agnostic filtering.

    Args:
        figure: A matplotlib ``Figure`` object.
        selection_color: CSS color for the selection highlight.
            Defaults to ``"#3b82f6"``.
        selection_opacity: Fill opacity for the selection area (0–1).
            Defaults to ``0.15``.
        stroke_width: Border width for the selection outline in pixels.
            Defaults to ``2``.
        debounce: If ``True``, the selection is only sent to Python on
            mouse-up. If ``False`` (the default), it streams while dragging.
        label: Markdown label for the element. Defaults to ``""``.
        on_change: Optional callback invoked when the selection changes.
    """

    name: Final[str] = "marimo-matplotlib"

    def __init__(
        self,
        figure: Figure,
        *,
        selection_color: str = "#3b82f6",
        selection_opacity: float = 0.15,
        stroke_width: float = 2,
        debounce: bool = False,
        label: str = "",
        on_change: Optional[Callable[[MatplotlibSelection], None]] = None,
    ) -> None:
        DependencyManager.matplotlib.require("for `mo.ui.matplotlib`")

        self._figure: Figure = figure

        ax = figure.axes[0] if figure.axes else None
        if ax is None:
            raise ValueError(
                "The figure must have at least one axes. "
                "Create a figure with `fig, ax = plt.subplots()` first."
            )

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
                "selection-color": selection_color,
                "selection-opacity": selection_opacity,
                "stroke-width": stroke_width,
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
            if not isinstance(data, dict):
                return None
            return {
                "type": "box",
                "data": {
                    "x_min": float(data["x_min"]),
                    "x_max": float(data["x_max"]),
                    "y_min": float(data["y_min"]),
                    "y_max": float(data["y_max"]),
                },
            }
        if sel_type == "lasso":
            if not isinstance(data, list):
                return None
            return {
                "type": "lasso",
                "data": [
                    (float(v[0]), float(v[1])) for v in data
                ],
            }
        return None

    def get_bounds(
        self,
    ) -> Optional[tuple[float, float, float, float]]:
        """Get the bounding box of the current selection.

        Returns:
            A tuple ``(x_min, x_max, y_min, y_max)``.
            For lasso selections, returns the bounding box of all vertices.
            Returns ``None`` if nothing is selected.
        """
        v = self.value
        if v is None:
            return None
        if v["type"] == "box":
            d = v["data"]
            return (d["x_min"], d["x_max"], d["y_min"], d["y_max"])
        # lasso
        xs = [p[0] for p in v["data"]]
        ys = [p[1] for p in v["data"]]
        return (min(xs), max(xs), min(ys), max(ys))

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
        if v["type"] == "box":
            d = v["data"]
            return [
                (d["x_min"], d["y_min"]),
                (d["x_max"], d["y_min"]),
                (d["x_max"], d["y_max"]),
                (d["x_min"], d["y_max"]),
            ]
        # lasso
        return list(v["data"])

    def contains_point(self, x: float, y: float) -> bool:
        """Test if a point is inside the current selection.

        Args:
            x: The x-coordinate to test.
            y: The y-coordinate to test.

        Returns:
            ``True`` if the point is inside the selection, ``False`` otherwise
            or if nothing is selected.
        """
        from matplotlib.path import Path  # type: ignore[import-untyped]

        v = self.value
        if v is None:
            return False
        if v["type"] == "box":
            d = v["data"]
            return (
                d["x_min"] <= x <= d["x_max"]
                and d["y_min"] <= y <= d["y_max"]
            )
        # lasso
        path = Path(v["data"])
        return bool(path.contains_point((x, y)))

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
        from matplotlib.path import Path  # type: ignore[import-untyped]

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)

        v = self.value
        if v is None:
            return np.zeros(len(x_arr), dtype=bool)

        if v["type"] == "box":
            d = v["data"]
            return (
                (x_arr >= d["x_min"])
                & (x_arr <= d["x_max"])
                & (y_arr >= d["y_min"])
                & (y_arr <= d["y_max"])
            )
        # lasso
        path = Path(v["data"])
        points = np.column_stack([x_arr, y_arr])
        return path.contains_points(points)

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

        mask = self.get_mask(x, y)
        return np.where(mask)[0]


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
