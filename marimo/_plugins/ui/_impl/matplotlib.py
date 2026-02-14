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

# Selection is a dictionary of the form:
# {"mode": "box", "has_selection": True,
#  "selection": {"x_min": ..., "x_max": ..., "y_min": ..., "y_max": ...}}
# or {} when nothing is selected.
MatplotlibSelection = dict[str, JSONType]


@mddoc
class matplotlib(UIElement[MatplotlibSelection, MatplotlibSelection]):
    """Make reactive selections on matplotlib charts.

    Use `mo.ui.matplotlib` to make matplotlib plots interactive: draw a box
    selection on the frontend, then use the selection geometry in Python
    to filter your data.

    The figure is rendered as a static image with an interactive box-selection
    overlay. The selection returns rectangular bounds in data coordinates.

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
        value (Dict[str, Any]): The raw selection data. Empty dict when nothing
            is selected. For box selections: ``{"mode": "box",
            "has_selection": True, "selection": {"x_min": ..., "x_max": ...,
            "y_min": ..., "y_max": ...}}``.

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
        self, value: MatplotlibSelection
    ) -> MatplotlibSelection:
        if not value or not value.get("has_selection"):
            return {}
        return value

    def get_bounds(
        self,
    ) -> Optional[tuple[float, float, float, float]]:
        """Get the bounding box of the current selection.

        Returns:
            A tuple ``(x_min, x_max, y_min, y_max)`` for box selections.
            Returns ``None`` if nothing is selected.
        """
        v = self.value
        if not v or not v.get("has_selection"):
            return None

        selection = v.get("selection", {})
        assert isinstance(selection, dict)

        return (
            float(selection["x_min"]),
            float(selection["x_max"]),
            float(selection["y_min"]),
            float(selection["y_max"]),
        )

    def get_vertices(self) -> list[tuple[float, float]]:
        """Get the vertices of the current selection.

        Returns:
            The 4 corners of the box selection rectangle.
            Returns an empty list if nothing is selected.
        """
        v = self.value
        if not v or not v.get("has_selection"):
            return []

        selection = v.get("selection", {})
        assert isinstance(selection, dict)

        x_min = float(selection["x_min"])
        x_max = float(selection["x_max"])
        y_min = float(selection["y_min"])
        y_max = float(selection["y_max"])
        return [
            (x_min, y_min),
            (x_max, y_min),
            (x_max, y_max),
            (x_min, y_max),
        ]

    def contains_point(self, x: float, y: float) -> bool:
        """Test if a point is inside the current selection.

        Args:
            x: The x-coordinate to test.
            y: The y-coordinate to test.

        Returns:
            ``True`` if the point is inside the selection, ``False`` otherwise
            or if nothing is selected.
        """
        v = self.value
        if not v or not v.get("has_selection"):
            return False

        selection = v.get("selection", {})
        assert isinstance(selection, dict)

        return (
            float(selection["x_min"]) <= x <= float(selection["x_max"])
            and float(selection["y_min"]) <= y <= float(selection["y_max"])
        )

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

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)

        v = self.value
        if not v or not v.get("has_selection"):
            return np.zeros(len(x_arr), dtype=bool)

        selection = v.get("selection", {})
        assert isinstance(selection, dict)

        x_min = float(selection["x_min"])
        x_max = float(selection["x_max"])
        y_min = float(selection["y_min"])
        y_max = float(selection["y_max"])
        return (
            (x_arr >= x_min)
            & (x_arr <= x_max)
            & (y_arr >= y_min)
            & (y_arr <= y_max)
        )

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
