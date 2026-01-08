# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Optional,
    cast,
)

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import plotly.graph_objects as go  # type:ignore

# Selection is a dictionary of the form:
# {
#   "points": {
#     "field1": "value1",
#     "field2": "value2",
#   }[],
#   "range": {
#     "field1": [min, max],
#     "field2": [min, max],
#   },
#  "indices": int[],
# }
PlotlySelection = dict[str, JSONType]


@mddoc
class plotly(UIElement[PlotlySelection, list[dict[str, Any]]]):
    """Make reactive plots with Plotly.

    Use `mo.ui.plotly` to make plotly plots reactive: select data with your
    cursor on the frontend, get them as a list of dicts in Python!

    This function supports scatter plots, line charts, bar charts, treemap charts,
    sunburst charts, and heatmaps.

    Examples:
        ```python
        import plotly.express as px
        import marimo as mo
        from vega_datasets import data

        _plot = px.scatter(
            data.cars(), x="Horsepower", y="Miles_per_Gallon", color="Origin"
        )

        plot = mo.ui.plotly(_plot)
        ```

        ```python
        # View the plot and selected data
        mo.hstack([plot, plot.value])
        ```

        Or with custom configuration:

        ```python
        plot = mo.ui.plotly(
            _plot,
            config={"staticPlot": True},
        )
        ```

    Attributes:
        value (Dict[str, Any]): A dict of the plot data.
        ranges (Dict[str, List[float]]): The selection of the plot; this may be an
            interval along the name of an axis.
        points (List[Dict[str, Any]]): The selected points data.
        indices (List[int]): The indices of selected points.

    Args:
        figure (plotly.graph_objects.Figure): A plotly Figure object.
        config (Optional[Dict[str, Any]], optional): Configuration for the plot.
            This is a dictionary that is passed directly to plotly.
            See the plotly documentation for more information:
            https://plotly.com/javascript/configuration-options/
            This takes precedence over the default configuration of the renderer.
            Defaults to None.
        renderer_name (Optional[str], optional): Renderer to use for the plot.
            If this is not provided, the default renderer (`pio.renderers.default`)
            is used. Defaults to None.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Optional[Callable[[JSONType], None]], optional): Callback to run
            when this element's value changes. Defaults to None.
    """

    name: Final[str] = "marimo-plotly"

    def __init__(
        self,
        figure: go.Figure,
        config: Optional[dict[str, Any]] = None,
        renderer_name: Optional[str] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[JSONType], None]] = None,
    ) -> None:
        DependencyManager.plotly.require("for `mo.ui.plotly`")

        import plotly.io as pio  # type:ignore

        # Store figure for later use in _convert_value
        self._figure: go.Figure = figure
        # Initialize selection data storage
        self._selection_data: PlotlySelection = {}

        json_str = pio.to_json(figure)

        resolved_config: dict[str, Any] = {}
        if config is not None:
            resolved_config = config
        else:
            try:
                resolved_name: str = renderer_name or cast(
                    str, pio.renderers.default
                )
                default_renderer: Any = (
                    pio.renderers[resolved_name]
                    if resolved_name and resolved_name in pio.renderers
                    else None
                )
                if default_renderer is not None:
                    resolved_config = default_renderer.config or {}
            except AttributeError:
                LOGGER.warning(
                    "Could not find default renderer configuration. "
                    "Using an empty configuration."
                )

        initial_value: dict[str, Any] = {}

        def add_selection(selection: go.layout.Selection) -> None:
            if not all(
                hasattr(selection, k) for k in ["x0", "x1", "y0", "y1"]
            ):
                return

            initial_value["range"] = {
                "x": [selection.x0, selection.x1],
                "y": [selection.y0, selection.y1],
            }

            # Find points within the selection range
            selected_points = []
            selected_indices = []

            x_axes: list[go.layout.XAxis] = []
            figure.for_each_xaxis(x_axes.append)
            [x_axis] = x_axes if len(x_axes) == 1 else [None]
            y_axes: list[go.layout.YAxis] = []
            figure.for_each_yaxis(y_axes.append)
            [y_axis] = y_axes if len(y_axes) == 1 else [None]

            for trace in figure.data:
                # Skip heatmap and bar traces - they're handled separately below
                if getattr(trace, "type", None) in ("heatmap", "bar"):
                    continue
                x_data = getattr(trace, "x", None)
                y_data = getattr(trace, "y", None)
                if x_data is None or y_data is None:
                    continue
                for point_idx, (x, y) in enumerate(zip(x_data, y_data)):
                    # Early exit if x is not in range
                    if not (selection.x0 <= x <= selection.x1):
                        continue
                    if selection.y0 <= y <= selection.y1:
                        selected_points.append(
                            {
                                axis.title.text: val
                                for axis, val in [(x_axis, x), (y_axis, y)]
                                if axis and axis.title.text
                            }
                        )
                        selected_indices.append(point_idx)

            initial_value["points"] = selected_points
            initial_value["indices"] = selected_indices

            # For heatmaps with a range selection, extract all cells in range
            has_heatmap = any(
                getattr(trace, "type", None) == "heatmap"
                for trace in figure.data
            )
            if has_heatmap and initial_value.get("range"):
                _append_heatmap_cells_to_selection(figure, initial_value)

            # Note: Bar chart extraction is handled in _convert_value, not here
            # This avoids duplicate extraction since _convert_value is called
            # during super().__init__() with the initial_value

        figure.for_each_selection(add_selection)

        super().__init__(
            component_name=plotly.name,
            initial_value=initial_value,
            label=label,
            args={
                "figure": json.loads(json_str),
                "config": resolved_config,
            },
            on_change=on_change,
        )

    @property
    def ranges(self) -> dict[str, list[float]]:
        """Get the range selection of the plot.

        Returns:
            Dict[str, List[float]]: A dictionary mapping field names to their
                selected ranges, where each range is a list of [min, max] values.
                Returns an empty dict if no range selection exists.
        """
        if not self._selection_data:
            return {}
        if "range" not in self._selection_data:
            return {}
        return self._selection_data["range"]  # type:ignore

    @property
    def points(self) -> list[dict[str, Any]]:
        """Get the selected points data from the plot.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing the data for
                each selected point. Returns an empty list if no points are selected.
        """
        if not self._selection_data:
            return []
        if "points" not in self._selection_data:
            return []
        return self._selection_data["points"]  # type:ignore

    @property
    def indices(self) -> list[int]:
        """Get the indices of selected points in the plot.

        Returns:
            List[int]: A list of indices corresponding to the selected points.
                Returns an empty list if no points are selected.
        """
        if not self._selection_data:
            return []
        if "indices" not in self._selection_data:
            return []
        return self._selection_data["indices"]  # type:ignore

    def _convert_value(self, value: PlotlySelection) -> Any:
        # Store the selection data
        self._selection_data = value

        has_heatmap = any(
            getattr(trace, "type", None) == "heatmap"
            for trace in self._figure.data
        )

        has_scatter = any(
            getattr(trace, "type", None) == "scatter"
            for trace in self._figure.data
        )

        # For heatmaps with a range selection, always extract all cells in range
        # (Plotly only sends corner/edge points, not all cells)
        if has_heatmap and value.get("range"):
            _append_heatmap_cells_to_selection(
                self._figure, self._selection_data
            )

        has_bar = any(
            getattr(trace, "type", None) == "bar"
            for trace in self._figure.data
        )

        # For bar charts with a range selection, extract all bars in range
        if has_bar and value.get("range"):
            _append_bar_items_to_selection(self._figure, self._selection_data)

        # For line/scatter charts with a range selection, extract all points in x-range
        # This handles mode='lines', mode='lines+markers', and mode='markers'
        # Plotly may not send point data for pure line charts, so we extract manually
        if has_scatter and value.get("range"):
            _append_scatter_points_to_selection(
                self._figure, self._selection_data
            )

        result = self.points
        return result


def _append_heatmap_cells_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Append heatmap cells within the selection range to the selection data.

    This modifies selection_data in place, appending any heatmap cells
    that fall within the range to the existing points and indices.
    """
    range_value = selection_data.get("range")
    if not isinstance(range_value, dict):
        return

    heatmap_cells = _extract_heatmap_cells_from_range(
        figure, cast(dict[str, Any], range_value)
    )
    if heatmap_cells:
        # Append heatmap cells to existing points (e.g., scatter)
        # Filter out empty dicts that may come from frontend
        existing_points = [p for p in selection_data.get("points", []) if p]
        existing_indices = selection_data.get("indices", [])
        selection_data["points"] = existing_points + heatmap_cells
        selection_data["indices"] = existing_indices + list(
            range(
                len(existing_indices),
                len(existing_indices) + len(heatmap_cells),
            )
        )


def _extract_heatmap_cells_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract heatmap cells that fall within a selection range."""

    if not range_data.get("x") or not range_data.get("y"):
        return []

    x_range = range_data["x"]
    y_range = range_data["y"]
    x_min, x_max = min(x_range), max(x_range)
    y_min, y_max = min(y_range), max(y_range)

    # Use numpy fast path if available for better performance on large heatmaps
    if DependencyManager.numpy.has():
        return _extract_heatmap_cells_numpy(figure, x_min, x_max, y_min, y_max)

    return _extract_heatmap_cells_fallback(figure, x_min, x_max, y_min, y_max)


def _extract_heatmap_cells_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract heatmap cells using numpy for O(selected) complexity."""
    import numpy as np

    selected_cells: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "heatmap":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        z_data = getattr(trace, "z", None)

        if x_data is None or y_data is None or z_data is None:
            continue

        # Convert to numpy arrays for vectorized operations
        x_arr = np.asarray(x_data)
        y_arr = np.asarray(y_data)
        z_arr = np.asarray(z_data)

        # Determine if axes are numeric
        x_is_numeric = np.issubdtype(x_arr.dtype, np.number)
        y_is_numeric = np.issubdtype(y_arr.dtype, np.number)

        # Compute masks for valid indices
        if x_is_numeric:
            x_mask = (x_arr >= x_min) & (x_arr <= x_max)
        else:
            # Categorical: cell spans (index - 0.5) to (index + 0.5)
            # Strict overlap: x_max > cell_x_min and x_min < cell_x_max
            x_indices = np.arange(len(x_arr))
            x_mask = (x_max > x_indices - 0.5) & (x_min < x_indices + 0.5)

        if y_is_numeric:
            y_mask = (y_arr >= y_min) & (y_arr <= y_max)
        else:
            # Categorical: cell spans (index - 0.5) to (index + 0.5)
            # Strict overlap: y_max > cell_y_min and y_min < cell_y_max
            y_indices = np.arange(len(y_arr))
            y_mask = (y_max > y_indices - 0.5) & (y_min < y_indices + 0.5)

        # Get indices where masks are True
        y_idx = np.where(y_mask)[0]
        x_idx = np.where(x_mask)[0]

        # Iterate only over selected indices (O(selected) instead of O(n*m))
        for i in y_idx:
            for j in x_idx:
                # Bounds check for z_data to handle malformed/ragged arrays
                if i >= len(z_arr) or j >= len(z_arr[i]):
                    continue
                selected_cells.append(
                    {
                        "x": x_data[j],
                        "y": y_data[i],
                        "z": z_arr[i][j].item()
                        if hasattr(z_arr[i][j], "item")
                        else z_arr[i][j],
                        "curveNumber": trace_idx,
                    }
                )

    return selected_cells


def _append_scatter_points_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Append scatter/line points within the selection range to the selection data.

    This modifies selection_data in place, appending any scatter/line points
    that fall within the x-range to the existing points and indices.

    For line charts, Plotly may not send point-level data in the selection event
    (especially for mode='lines'). We manually extract all points where x is
    within the selected range to match Altair's behavior.
    """
    range_value = selection_data.get("range")
    if not isinstance(range_value, dict):
        return

    scatter_points = _extract_scatter_points_from_range(
        figure, cast(dict[str, Any], range_value)
    )
    if scatter_points:
        # Get existing points and indices
        existing_points = selection_data.get("points", [])
        existing_indices = selection_data.get("indices", [])

        # Filter out empty dicts from existing points (these come from line charts)
        # where Plotly sends the structure but no data
        existing_points = [p for p in existing_points if p]

        # Merge with scatter points, avoiding duplicates
        # Use pointIndex and curveNumber to track uniqueness
        # (can't use x/y values since field names vary: "x"/"y" vs "X"/"Y" etc.)
        seen = set()
        merged_points = []
        merged_indices = []

        # Add existing points first
        for idx, point in enumerate(existing_points):
            key = (
                point.get("pointIndex"),
                point.get("curveNumber"),
            )
            if key not in seen and key != (None, None):
                seen.add(key)
                merged_points.append(point)
                if idx < len(existing_indices):
                    merged_indices.append(existing_indices[idx])

        # Add new scatter points
        for point in scatter_points:
            key = (
                point.get("pointIndex"),
                point.get("curveNumber"),
            )
            if key not in seen:
                seen.add(key)
                merged_points.append(point)
                # Indices for manually extracted points - use the point's original index
                if "pointIndex" in point:
                    merged_indices.append(point["pointIndex"])

        selection_data["points"] = merged_points
        selection_data["indices"] = merged_indices


def _extract_scatter_points_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract scatter/line points that fall within a selection range.

    This follows Altair's behavior: returns all points where x is within
    the x-range, regardless of y value.
    """
    if not range_data.get("x"):
        return []

    x_range = range_data["x"]
    x_min, x_max = min(x_range), max(x_range)

    # Use numpy fast path if available for better performance
    if DependencyManager.numpy.has():
        return _extract_scatter_points_numpy(figure, x_min, x_max)

    return _extract_scatter_points_fallback(figure, x_min, x_max)


def _extract_scatter_points_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
) -> list[dict[str, Any]]:
    """Extract scatter/line points using numpy for better performance."""
    import numpy as np

    selected_points: list[dict[str, Any]] = []

    # Get axis titles for field naming
    x_axes: list[go.layout.XAxis] = []
    figure.for_each_xaxis(x_axes.append)
    x_axis = x_axes[0] if len(x_axes) == 1 else None

    y_axes: list[go.layout.YAxis] = []
    figure.for_each_yaxis(y_axes.append)
    y_axis = y_axes[0] if len(y_axes) == 1 else None

    x_field = x_axis.title.text if (x_axis and x_axis.title.text) else "x"
    y_field = y_axis.title.text if (y_axis and y_axis.title.text) else "y"

    for trace_idx, trace in enumerate(figure.data):
        # Only process scatter traces (which includes lines, markers, lines+markers)
        if getattr(trace, "type", None) != "scatter":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)

        if x_data is None or y_data is None:
            continue

        # Convert to numpy arrays for vectorized operations
        x_arr = np.asarray(x_data)
        y_arr = np.asarray(y_data)

        # Check if x is numeric
        x_is_numeric = np.issubdtype(x_arr.dtype, np.number)

        # Filter by x-range (matching Altair behavior)
        if x_is_numeric:
            x_mask = (x_arr >= x_min) & (x_arr <= x_max)
        else:
            # Categorical: use index-based filtering
            x_indices = np.arange(len(x_arr))
            x_mask = (x_max > x_indices - 0.5) & (x_min < x_indices + 0.5)

        # Get indices where mask is True
        selected_indices = np.where(x_mask)[0]

        # Build point dicts for selected indices
        for idx in selected_indices:
            # Use .item() to convert numpy types to Python types
            x_val = (
                x_arr[idx].item()
                if hasattr(x_arr[idx], "item")
                else x_arr[idx]
            )
            y_val = (
                y_arr[idx].item()
                if hasattr(y_arr[idx], "item")
                else y_arr[idx]
            )

            point_dict = {
                x_field: x_val,
                y_field: y_val,
                "curveNumber": trace_idx,
                "pointIndex": int(idx),
            }

            # Add trace name if available
            if hasattr(trace, "name") and trace.name:
                point_dict["name"] = trace.name

            selected_points.append(point_dict)

    return selected_points


def _extract_scatter_points_fallback(
    figure: go.Figure,
    x_min: float,
    x_max: float,
) -> list[dict[str, Any]]:
    """Extract scatter/line points using pure Python (fallback when numpy unavailable)."""
    selected_points: list[dict[str, Any]] = []

    # Get axis titles for field naming
    x_axes: list[go.layout.XAxis] = []
    figure.for_each_xaxis(x_axes.append)
    x_axis = x_axes[0] if len(x_axes) == 1 else None

    y_axes: list[go.layout.YAxis] = []
    figure.for_each_yaxis(y_axes.append)
    y_axis = y_axes[0] if len(y_axes) == 1 else None

    x_field = x_axis.title.text if (x_axis and x_axis.title.text) else "x"
    y_field = y_axis.title.text if (y_axis and y_axis.title.text) else "y"

    for trace_idx, trace in enumerate(figure.data):
        # Only process scatter traces (which includes lines, markers, lines+markers)
        if getattr(trace, "type", None) != "scatter":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)

        if x_data is None or y_data is None:
            continue

        # Iterate through points and filter by x-range
        for point_idx, (x_val, y_val) in enumerate(zip(x_data, y_data)):
            # Check if x is within range
            x_in_range = False

            if isinstance(x_val, (int, float)):
                x_in_range = x_min <= x_val <= x_max
            else:
                # Categorical - use index-based filtering
                cell_x_min = point_idx - 0.5
                cell_x_max = point_idx + 0.5
                x_in_range = not (x_max <= cell_x_min or x_min >= cell_x_max)

            if x_in_range:
                point_dict = {
                    x_field: x_val,
                    y_field: y_val,
                    "curveNumber": trace_idx,
                    "pointIndex": point_idx,
                }

                # Add trace name if available
                if hasattr(trace, "name") and trace.name:
                    point_dict["name"] = trace.name

                selected_points.append(point_dict)

    return selected_points


def _extract_heatmap_cells_fallback(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract heatmap cells using pure Python (fallback when numpy unavailable)."""
    selected_cells: list[dict[str, Any]] = []

    # Iterate through traces to find heatmaps
    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "heatmap":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        z_data = getattr(trace, "z", None)

        if x_data is None or y_data is None or z_data is None:
            continue

        # Iterate through the heatmap cells
        for i, y_val in enumerate(y_data):
            for j, x_val in enumerate(x_data):
                # Check if cell is within selection range
                # Handle both numeric and categorical data
                x_in_range = False
                y_in_range = False

                if isinstance(x_val, (int, float)):
                    x_in_range = x_min <= x_val <= x_max
                else:
                    # Categorical - each cell spans from (index - 0.5) to (index + 0.5)
                    # Include cell if selection range strictly overlaps with cell bounds
                    cell_x_min = j - 0.5
                    cell_x_max = j + 0.5
                    x_in_range = not (
                        x_max <= cell_x_min or x_min >= cell_x_max
                    )

                if isinstance(y_val, (int, float)):
                    y_in_range = y_min <= y_val <= y_max
                else:
                    # Categorical - each cell spans from (index - 0.5) to (index + 0.5)
                    # Include cell if selection range strictly overlaps with cell bounds
                    cell_y_min = i - 0.5
                    cell_y_max = i + 0.5
                    y_in_range = not (
                        y_max <= cell_y_min or y_min >= cell_y_max
                    )

                if x_in_range and y_in_range:
                    # Bounds check for z_data to handle malformed/ragged arrays
                    if i >= len(z_data) or j >= len(z_data[i]):
                        continue
                    selected_cells.append(
                        {
                            "x": x_val,
                            "y": y_val,
                            "z": z_data[i][j],
                            "curveNumber": trace_idx,
                        }
                    )

    return selected_cells


def _append_bar_items_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Append bars within the selection range to the selection data.

    This modifies selection_data in place, appending any bars
    that fall within the range to the existing points and indices.
    """
    range_value = selection_data.get("range")
    if not isinstance(range_value, dict):
        return

    bar_items = _extract_bars_from_range(
        figure, cast(dict[str, Any], range_value)
    )
    if bar_items:
        # Append bar items to existing points (e.g., scatter)
        # Filter out empty dicts that may come from frontend
        existing_points = [p for p in selection_data.get("points", []) if p]
        existing_indices = selection_data.get("indices", [])
        selection_data["points"] = existing_points + bar_items
        selection_data["indices"] = existing_indices + list(
            range(
                len(existing_indices),
                len(existing_indices) + len(bar_items),
            )
        )


def _extract_bars_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract bars that fall within a selection range."""

    if not range_data.get("x") or not range_data.get("y"):
        return []

    x_range = range_data["x"]
    y_range = range_data["y"]
    x_min, x_max = min(x_range), max(x_range)
    y_min, y_max = min(y_range), max(y_range)

    # Use numpy fast path if available for better performance on large datasets
    if DependencyManager.numpy.has():
        return _extract_bars_numpy(figure, x_min, x_max, y_min, y_max)

    return _extract_bars_fallback(figure, x_min, x_max, y_min, y_max)


def _extract_bars_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract bars using numpy for O(selected) complexity."""
    import numpy as np

    selected_bars: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "bar":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)

        if x_data is None or y_data is None:
            continue

        # Determine bar orientation (default is 'v' for vertical)
        orientation = getattr(trace, "orientation", "v")
        if orientation is None:
            orientation = "v"

        # Convert to numpy arrays for vectorized operations
        x_arr = np.asarray(x_data)
        y_arr = np.asarray(y_data)

        # For vertical bars: filter by x-axis position
        # For horizontal bars: filter by y-axis position (swap roles)
        if orientation == "v":
            # Vertical bars: x-axis determines which bars are selected
            # y-axis is the value (we don't filter by it, similar to Altair)
            position_data = x_arr
            value_data = y_arr
            pos_min, pos_max = x_min, x_max
        else:  # orientation == "h"
            # Horizontal bars: y-axis determines which bars are selected
            # x-axis is the value
            position_data = y_arr
            value_data = x_arr
            pos_min, pos_max = y_min, y_max

        # Determine if position axis is numeric or categorical
        pos_is_numeric = np.issubdtype(position_data.dtype, np.number)

        # Compute mask for valid indices
        if pos_is_numeric:
            # Numeric axis: direct range comparison
            # TODO: Consider bar width in future implementations
            # Currently treating bars as points at their position value
            pos_mask = (position_data >= pos_min) & (position_data <= pos_max)
        else:
            # Categorical axis: each bar spans (index - 0.5) to (index + 0.5)
            # Selection overlaps if: pos_max > bar_min AND pos_min < bar_max
            pos_indices = np.arange(len(position_data))
            pos_mask = (pos_max > pos_indices - 0.5) & (
                pos_min < pos_indices + 0.5
            )

        # Get indices where mask is True
        selected_indices = np.where(pos_mask)[0]

        # Iterate only over selected indices
        for i in selected_indices:
            if orientation == "v":
                selected_bars.append(
                    {
                        "x": x_data[i],
                        "y": value_data[i].item()
                        if hasattr(value_data[i], "item")
                        else value_data[i],
                        "curveNumber": trace_idx,
                    }
                )
            else:  # horizontal
                selected_bars.append(
                    {
                        "x": value_data[i].item()
                        if hasattr(value_data[i], "item")
                        else value_data[i],
                        "y": y_data[i],
                        "curveNumber": trace_idx,
                    }
                )

    return selected_bars


def _extract_bars_fallback(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract bars using pure Python (fallback when numpy unavailable)."""
    selected_bars: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "bar":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)

        if x_data is None or y_data is None:
            continue

        # Determine bar orientation (default is 'v' for vertical)
        orientation = getattr(trace, "orientation", "v")
        if orientation is None:
            orientation = "v"

        # For vertical bars: filter by x-axis position
        # For horizontal bars: filter by y-axis position
        if orientation == "v":
            position_data = x_data
            value_data = y_data
            pos_min, pos_max = x_min, x_max
        else:  # orientation == "h"
            position_data = y_data
            value_data = x_data
            pos_min, pos_max = y_min, y_max

        # Iterate through bars
        for i, pos_val in enumerate(position_data):
            # Check if bar position is within selection range
            pos_in_range = False

            if isinstance(pos_val, (int, float)):
                # Numeric axis: direct comparison
                # TODO: Consider bar width in future implementations
                # Currently treating bars as points at their position value
                pos_in_range = pos_min <= pos_val <= pos_max
            else:
                # Categorical axis: each bar spans (index - 0.5) to (index + 0.5)
                # Include bar if selection range strictly overlaps with bar bounds
                bar_min = i - 0.5
                bar_max = i + 0.5
                pos_in_range = not (pos_max <= bar_min or pos_min >= bar_max)

            if pos_in_range:
                if orientation == "v":
                    selected_bars.append(
                        {
                            "x": x_data[i],
                            "y": value_data[i],
                            "curveNumber": trace_idx,
                        }
                    )
                else:  # horizontal
                    selected_bars.append(
                        {
                            "x": value_data[i],
                            "y": y_data[i],
                            "curveNumber": trace_idx,
                        }
                    )

    return selected_bars
