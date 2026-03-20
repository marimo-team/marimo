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
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.hypertext import is_non_interactive
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


def _is_orderable_value(value: Any) -> bool:
    """Check if a value is orderable (numeric or datetime-like).

    Used by fallback functions to determine if direct comparison is possible.
    """
    import datetime

    if isinstance(value, (int, float, datetime.datetime, datetime.date)):
        return True

    # Check for ISO format datetime strings (sent from frontend via JSON)
    if isinstance(value, str):
        try:
            datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except (ValueError, AttributeError):
            pass

    return False


def _parse_datetime_bound(value: Any) -> Any:
    """Parse a bound value that might be a datetime string from the frontend.

    Returns the original value if it's already a datetime or not a valid
    datetime string.
    """
    import datetime

    if isinstance(value, (datetime.datetime, datetime.date)):
        return value

    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            pass

    return value


def _is_orderable_axis(arr: Any, bound_value: Any) -> bool:
    """Check if an axis contains orderable (numeric/datetime) values.

    This checks both numpy dtype and the actual element types to handle:
    - Native numpy numeric/datetime64 arrays
    - Object arrays containing Python datetime.datetime objects
    - Datetime strings from frontend JSON (ISO format)

    Args:
        arr: A numpy array of axis values
        bound_value: A sample bound value (e.g., x_min) to check compatibility

    Returns:
        True if the axis values can be compared with the bound values
    """
    import datetime

    import numpy as np

    # Check numpy dtype first (handles native numpy types)
    if np.issubdtype(arr.dtype, np.number):
        return True
    if np.issubdtype(arr.dtype, np.datetime64):
        return True

    # For object arrays, check element types and bound value compatibility
    if arr.dtype == np.object_ and len(arr) > 0:
        first_elem = arr[0]
        # Check if elements are datetime-like
        if isinstance(first_elem, (datetime.datetime, datetime.date)):
            # Bound can be datetime object or ISO string from frontend
            if isinstance(bound_value, (datetime.datetime, datetime.date)):
                return True
            # Check for ISO format datetime strings (sent from frontend via JSON)
            if isinstance(bound_value, str):
                try:
                    datetime.datetime.fromisoformat(
                        bound_value.replace("Z", "+00:00")
                    )
                    return True
                except (ValueError, AttributeError):
                    pass

    return False


@mddoc
class plotly(UIElement[PlotlySelection, list[dict[str, Any]]]):
    """Make reactive plots with Plotly.

    Use `mo.ui.plotly` to make plotly plots reactive: select data with your
    cursor on the frontend, get them as a list of dicts in Python!

    This function supports scatter plots, scattergl plots, line charts, area
    charts, bar charts, histograms, treemap charts, sunburst charts, and heatmaps.

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
                # Skip trace types handled separately in _convert_value
                if getattr(trace, "type", None) in (
                    "heatmap",
                    "bar",
                    "histogram",
                ):
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

    # Override _mime_ to return plotly HTML in non-JS environments
    def _mime_(self) -> tuple[KnownMimeType, str]:
        if is_non_interactive():
            return ("text/html", self._figure._repr_html_())
        return ("text/html", self.text)

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

        scatter_trace_types = {"scatter", "scattergl"}
        has_scatter = any(
            getattr(trace, "type", None) in scatter_trace_types
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

        # For scatter-like traces with a range selection, preserve Plotly's
        # explicit point payload when available and only fall back to x-range
        # extraction for traces that do not provide point-level selections.
        if has_scatter and value.get("range"):
            _append_scatter_points_to_selection(
                self._figure, self._selection_data
            )

        has_histogram = any(
            getattr(trace, "type", None) == "histogram"
            for trace in self._figure.data
        )

        # For histograms, convert selected bins/ranges to underlying sample rows.
        # This enables row-level reactive workflows from histogram selections.
        if has_histogram:
            _append_histogram_points_to_selection(
                self._figure, self._selection_data
            )

        # Check for map-based scatter traces (scattermap, scattermapbox, scattergeo)
        # These use lat/lon instead of x/y
        map_scatter_types = ("scattermap", "scattermapbox", "scattergeo")
        has_map_scatter = any(
            getattr(trace, "type", None) in map_scatter_types
            for trace in self._figure.data
        )

        # For map scatter traces, extract points from the selection
        # Unlike regular scatter, map selections don't have a "range" - they have
        # direct point selection via lasso/box select on the map
        if has_map_scatter:
            _append_map_scatter_points_to_selection(
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

        # Determine if axes are orderable (numeric or datetime-like)
        x_is_orderable = _is_orderable_axis(x_arr, x_min)
        y_is_orderable = _is_orderable_axis(y_arr, y_min)

        # Parse datetime bounds (frontend sends ISO strings via JSON)
        x_min_parsed = (
            _parse_datetime_bound(x_min) if x_is_orderable else x_min
        )
        x_max_parsed = (
            _parse_datetime_bound(x_max) if x_is_orderable else x_max
        )
        y_min_parsed = (
            _parse_datetime_bound(y_min) if y_is_orderable else y_min
        )
        y_max_parsed = (
            _parse_datetime_bound(y_max) if y_is_orderable else y_max
        )

        # Compute masks for valid indices
        if x_is_orderable:
            x_mask = (x_arr >= x_min_parsed) & (x_arr <= x_max_parsed)
        else:
            # Categorical: cell spans (index - 0.5) to (index + 0.5)
            # Strict overlap: x_max > cell_x_min and x_min < cell_x_max
            x_indices = np.arange(len(x_arr))
            x_mask = (x_max > x_indices - 0.5) & (x_min < x_indices + 0.5)

        if y_is_orderable:
            y_mask = (y_arr >= y_min_parsed) & (y_arr <= y_max_parsed)
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
    """Append fallback scatter/scattergl/line points to selection data.

    This modifies selection_data in place, appending x-range points only for
    scatter-like traces that need fallback extraction.

    Plotly box/lasso selections already include exact point payloads for marker
    traces, so we keep those as-is. For traces that do not provide point-level
    selections, such as pure lines, we manually extract all points where x is
    within the selected range to preserve the existing line-chart behavior.
    """
    range_value = selection_data.get("range")
    if not isinstance(range_value, dict):
        return

    # Filter out empty dicts from existing points (these come from line charts)
    # where Plotly sends the structure but no data.
    existing_points = [p for p in selection_data.get("points", []) if p]
    existing_indices = selection_data.get("indices", [])

    scatter_trace_indices = [
        idx
        for idx, trace in enumerate(figure.data)
        if getattr(trace, "type", None) in {"scatter", "scattergl"}
    ]

    explicit_curve_numbers = {
        curve_number
        for point in existing_points
        if isinstance((curve_number := point.get("curveNumber")), int)
        and curve_number in scatter_trace_indices
    }
    if (
        existing_points
        and not explicit_curve_numbers
        and not any("curveNumber" in point for point in existing_points)
        and len(scatter_trace_indices) == 1
    ):
        explicit_curve_numbers.add(scatter_trace_indices[0])

    scatter_points = _extract_scatter_points_from_range(
        figure,
        cast(dict[str, Any], range_value),
        trace_filter=lambda trace_idx, trace: (
            trace_idx not in explicit_curve_numbers
            and _trace_needs_scatter_range_fallback(trace)
        ),
    )
    if scatter_points or existing_points:
        # Merge with scatter points, avoiding duplicates
        # Use pointIndex and curveNumber to track uniqueness
        # (can't use x/y values since field names vary: "x"/"y" vs "X"/"Y" etc.)
        seen = set()
        merged_points = []
        merged_indices = []

        # Add existing points first
        for idx, point in enumerate(existing_points):
            point_index = point.get("pointIndex")
            curve_number = point.get("curveNumber")
            # Only de-duplicate when both pointIndex and curveNumber are present.
            # Non-scatter points (e.g., bar/heatmap) may not have pointIndex and
            # should not be collapsed down to a single item per trace.
            if point_index is not None and curve_number is not None:
                key = (point_index, curve_number)
                if key in seen:
                    continue
                seen.add(key)
            merged_points.append(point)
            if idx < len(existing_indices):
                merged_indices.append(existing_indices[idx])

        # Add new scatter points
        for point in scatter_points:
            point_index = point.get("pointIndex")
            curve_number = point.get("curveNumber")
            # As above, only de-duplicate when both identifiers are available.
            if point_index is not None and curve_number is not None:
                key = (point_index, curve_number)
                if key in seen:
                    continue
                seen.add(key)
            merged_points.append(point)
            # Indices for manually extracted points - use the point's original index
            if "pointIndex" in point:
                merged_indices.append(point["pointIndex"])

        selection_data["points"] = merged_points
        selection_data["indices"] = merged_indices


def _trace_needs_scatter_range_fallback(trace: Any) -> bool:
    """Return whether a scatter-like trace needs manual range extraction."""
    if getattr(trace, "type", None) not in {"scatter", "scattergl"}:
        return False

    mode = getattr(trace, "mode", None)
    if isinstance(mode, str) and "markers" in mode:
        return False

    return True


def _extract_scatter_points_from_range(
    figure: go.Figure,
    range_data: dict[str, Any],
    trace_filter: Optional[Callable[[int, Any], bool]] = None,
) -> list[dict[str, Any]]:
    """Extract scatter/scattergl/line points in a selection range.

    This follows Altair's behavior: returns all points where x is within
    the x-range, regardless of y value.
    """
    if not range_data.get("x"):
        return []

    x_range = range_data["x"]
    x_min, x_max = min(x_range), max(x_range)

    # Use numpy fast path if available for better performance
    if DependencyManager.numpy.has():
        return _extract_scatter_points_numpy(
            figure, x_min, x_max, trace_filter=trace_filter
        )

    return _extract_scatter_points_fallback(
        figure, x_min, x_max, trace_filter=trace_filter
    )


def _extract_scatter_points_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    trace_filter: Optional[Callable[[int, Any], bool]] = None,
) -> list[dict[str, Any]]:
    """Extract scatter/scattergl/line points using numpy."""
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
        # Process scatter-like traces (includes lines, markers, lines+markers)
        if getattr(trace, "type", None) not in {"scatter", "scattergl"}:
            continue
        if trace_filter is not None and not trace_filter(trace_idx, trace):
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)

        if x_data is None or y_data is None:
            continue

        # Convert to numpy arrays for vectorized operations
        x_arr = np.asarray(x_data)
        y_arr = np.asarray(y_data)

        # Check if x is orderable (numeric or datetime-like)
        x_is_orderable = _is_orderable_axis(x_arr, x_min)

        # Parse datetime bounds (frontend sends ISO strings via JSON)
        x_min_parsed = (
            _parse_datetime_bound(x_min) if x_is_orderable else x_min
        )
        x_max_parsed = (
            _parse_datetime_bound(x_max) if x_is_orderable else x_max
        )

        # Filter by x-range (matching Altair behavior)
        if x_is_orderable:
            x_mask = (x_arr >= x_min_parsed) & (x_arr <= x_max_parsed)
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
    trace_filter: Optional[Callable[[int, Any], bool]] = None,
) -> list[dict[str, Any]]:
    """Extract scatter/scattergl/line points with pure Python."""
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
        # Process scatter-like traces (includes lines, markers, lines+markers)
        if getattr(trace, "type", None) not in {"scatter", "scattergl"}:
            continue
        if trace_filter is not None and not trace_filter(trace_idx, trace):
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)

        if x_data is None or y_data is None:
            continue

        # Iterate through points and filter by x-range
        for point_idx, (x_val, y_val) in enumerate(zip(x_data, y_data)):
            # Check if x is within range
            x_in_range = False

            if _is_orderable_value(x_val) and _is_orderable_value(x_min):
                # Parse datetime bounds (frontend sends ISO strings)
                x_min_p = _parse_datetime_bound(x_min)
                x_max_p = _parse_datetime_bound(x_max)
                x_in_range = x_min_p <= x_val <= x_max_p
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

                if _is_orderable_value(x_val) and _is_orderable_value(x_min):
                    # Parse datetime bounds (frontend sends ISO strings)
                    x_min_p = _parse_datetime_bound(x_min)
                    x_max_p = _parse_datetime_bound(x_max)
                    x_in_range = x_min_p <= x_val <= x_max_p
                else:
                    # Categorical - each cell spans from (index - 0.5) to (index + 0.5)
                    # Include cell if selection range strictly overlaps with cell bounds
                    cell_x_min = j - 0.5
                    cell_x_max = j + 0.5
                    x_in_range = not (
                        x_max <= cell_x_min or x_min >= cell_x_max
                    )

                if _is_orderable_value(y_val) and _is_orderable_value(y_min):
                    # Parse datetime bounds (frontend sends ISO strings)
                    y_min_p = _parse_datetime_bound(y_min)
                    y_max_p = _parse_datetime_bound(y_max)
                    y_in_range = y_min_p <= y_val <= y_max_p
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


def _append_histogram_points_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Append histogram sample rows to selection data.

    Histogram selection events are bin-level on the frontend. This function
    converts selected bins/ranges to underlying sample rows so .value behaves
    like row-level selections from scatter plots.
    """
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))
    range_value = selection_data.get("range")

    histogram_points: list[dict[str, Any]] = []

    if isinstance(range_value, dict):
        histogram_points = _extract_histogram_points_from_range(
            figure, cast(dict[str, Any], range_value)
        )

    # Lasso selections may not include a rectangular range. In that case, use
    # the selected histogram bin payload (pointNumbers) to recover samples.
    if not histogram_points:
        histogram_points = _extract_histogram_points_from_bins(
            figure, all_points
        )

    if not histogram_points:
        return

    histogram_curve_numbers = {
        trace_idx
        for trace_idx, trace in enumerate(figure.data)
        if getattr(trace, "type", None) == "histogram"
    }

    # Drop existing histogram bin-level points, keep points from other traces.
    filtered_points: list[dict[str, Any]] = []
    filtered_indices: list[int] = []
    seen = set()

    for point_idx, point in enumerate(all_points):
        if not point:
            continue

        curve_number = point.get("curveNumber")
        if curve_number in histogram_curve_numbers:
            continue

        filtered_points.append(point)
        if point_idx < len(all_indices) and isinstance(
            all_indices[point_idx], int
        ):
            filtered_indices.append(all_indices[point_idx])
        elif isinstance(point.get("pointIndex"), int):
            filtered_indices.append(point["pointIndex"])

        key = (point.get("pointIndex"), point.get("curveNumber"))
        if key != (None, None):
            seen.add(key)

    # Merge histogram sample rows with deduplication by (curveNumber, pointIndex).
    for point in histogram_points:
        key = (point.get("pointIndex"), point.get("curveNumber"))
        if key in seen:
            continue
        seen.add(key)
        filtered_points.append(point)
        if "pointIndex" in point:
            filtered_indices.append(cast(int, point["pointIndex"]))

    selection_data["points"] = filtered_points
    selection_data["indices"] = filtered_indices


def _extract_histogram_points_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract histogram sample rows that fall in a selection range."""
    if DependencyManager.numpy.has():
        return _extract_histogram_points_numpy(figure, range_data)
    return _extract_histogram_points_fallback(figure, range_data)


def _extract_histogram_points_numpy(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract histogram sample rows using numpy for better performance."""
    import numpy as np

    selected_points: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "histogram":
            continue

        orientation = getattr(trace, "orientation", "v")
        if orientation is None:
            orientation = "v"

        axis_key = "y" if orientation == "h" else "x"
        axis_range = range_data.get(axis_key)
        axis_data = getattr(trace, axis_key, None)

        if axis_data is None or not axis_range:
            continue

        axis_min, axis_max = min(axis_range), max(axis_range)
        axis_arr = np.asarray(axis_data)

        if axis_arr.size == 0:
            continue

        axis_is_orderable = _is_orderable_axis(axis_arr, axis_min)
        axis_min_parsed = (
            _parse_datetime_bound(axis_min) if axis_is_orderable else axis_min
        )
        axis_max_parsed = (
            _parse_datetime_bound(axis_max) if axis_is_orderable else axis_max
        )

        if axis_is_orderable:
            axis_mask = (axis_arr >= axis_min_parsed) & (
                axis_arr <= axis_max_parsed
            )
        else:
            category_positions = {
                value: idx
                for idx, value in enumerate(dict.fromkeys(axis_data))
            }
            position_arr = np.asarray(
                [category_positions[value] for value in axis_data]
            )
            axis_mask = (axis_max > position_arr - 0.5) & (
                axis_min < position_arr + 0.5
            )

        selected_indices = np.where(axis_mask)[0]
        for point_idx in selected_indices:
            point = _build_histogram_sample_point(
                trace, trace_idx, int(point_idx)
            )
            if point is not None:
                selected_points.append(point)

    return selected_points


def _extract_histogram_points_fallback(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract histogram sample rows using pure Python."""
    selected_points: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "histogram":
            continue

        orientation = getattr(trace, "orientation", "v")
        if orientation is None:
            orientation = "v"

        axis_key = "y" if orientation == "h" else "x"
        axis_range = range_data.get(axis_key)
        axis_data = getattr(trace, axis_key, None)

        if axis_data is None or not axis_range:
            continue

        axis_min, axis_max = min(axis_range), max(axis_range)
        category_positions = {
            value: idx for idx, value in enumerate(dict.fromkeys(axis_data))
        }

        for point_idx, axis_value in enumerate(axis_data):
            axis_in_range = False

            if _is_orderable_value(axis_value) and _is_orderable_value(
                axis_min
            ):
                axis_min_p = _parse_datetime_bound(axis_min)
                axis_max_p = _parse_datetime_bound(axis_max)
                axis_in_range = axis_min_p <= axis_value <= axis_max_p
            else:
                position = category_positions[axis_value]
                bin_min = position - 0.5
                bin_max = position + 0.5
                axis_in_range = not (
                    axis_max <= bin_min or axis_min >= bin_max
                )

            if axis_in_range:
                point = _build_histogram_sample_point(
                    trace, trace_idx, point_idx
                )
                if point is not None:
                    selected_points.append(point)

    return selected_points


def _extract_histogram_points_from_bins(
    figure: go.Figure, points: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Extract histogram sample rows from selected bin payloads."""
    selected_points: list[dict[str, Any]] = []

    for point in points:
        curve_number = point.get("curveNumber")
        if not isinstance(curve_number, int):
            continue
        if not (0 <= curve_number < len(figure.data)):
            continue

        trace = figure.data[curve_number]
        if getattr(trace, "type", None) != "histogram":
            continue

        point_numbers = point.get("pointNumbers")
        if not isinstance(point_numbers, list):
            continue

        for point_number in point_numbers:
            if not isinstance(point_number, int):
                continue
            sample_point = _build_histogram_sample_point(
                trace, curve_number, point_number
            )
            if sample_point is not None:
                selected_points.append(sample_point)

    return selected_points


def _build_histogram_sample_point(
    trace: Any, trace_idx: int, point_idx: int
) -> Optional[dict[str, Any]]:
    """Build a row-level selection payload point from a histogram trace."""
    orientation = getattr(trace, "orientation", "v")
    if orientation is None:
        orientation = "v"

    axis_key = "y" if orientation == "h" else "x"
    paired_axis_key = "x" if orientation == "h" else "y"

    axis_value = _get_indexed_value(getattr(trace, axis_key, None), point_idx)
    if axis_value is None:
        return None

    point: dict[str, Any] = {
        axis_key: axis_value,
        "pointIndex": point_idx,
        "curveNumber": trace_idx,
    }

    paired_axis_value = _get_indexed_value(
        getattr(trace, paired_axis_key, None), point_idx
    )
    if paired_axis_value is not None:
        point[paired_axis_key] = paired_axis_value

    name = getattr(trace, "name", None)
    if name:
        point["name"] = name

    customdata = _get_indexed_value(
        getattr(trace, "customdata", None), point_idx
    )
    if customdata is not None:
        point["customdata"] = customdata

    text = _get_indexed_value(getattr(trace, "text", None), point_idx)
    if text is not None:
        point["text"] = text

    hovertext = _get_indexed_value(
        getattr(trace, "hovertext", None), point_idx
    )
    if hovertext is not None:
        point["hovertext"] = hovertext

    return point


def _get_indexed_value(data: Any, index: int) -> Any:
    """Safely extract an indexed value from array-like or scalar data."""
    if data is None:
        return None

    if isinstance(data, str):
        return data

    try:
        if not (0 <= index < len(data)):
            return None
    except TypeError:
        # Scalar value
        return data

    value = data[index]
    return value.item() if hasattr(value, "item") else value


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
    existing_points = [p for p in selection_data.get("points", []) if p]
    existing_indices = selection_data.get("indices", [])

    if not existing_points and not bar_items:
        return

    seen: set[tuple[int, int]] = set()
    merged_points: list[dict[str, Any]] = []
    merged_indices: list[int] = []

    for idx, point in enumerate(existing_points):
        point_id = _get_selection_point_id(point)
        if point_id is not None:
            if point_id in seen:
                continue
            seen.add(point_id)
        merged_points.append(point)
        if idx < len(existing_indices):
            merged_indices.append(existing_indices[idx])
        elif point_id is not None:
            merged_indices.append(point_id[1])

    for point in bar_items:
        point_id = _get_selection_point_id(point)
        if point_id is not None:
            if point_id in seen:
                continue
            seen.add(point_id)
            merged_indices.append(point_id[1])
        merged_points.append(point)

    selection_data["points"] = merged_points
    selection_data["indices"] = merged_indices


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

        if orientation == "v":
            position_data = x_arr
            value_data = y_arr
            pos_min, pos_max = x_min, x_max
            value_min, value_max = y_min, y_max
        else:  # orientation == "h"
            position_data = y_arr
            value_data = x_arr
            pos_min, pos_max = y_min, y_max
            value_min, value_max = x_min, x_max

        pos_is_orderable = _is_orderable_axis(position_data, pos_min)
        pos_min_parsed = (
            _parse_datetime_bound(pos_min) if pos_is_orderable else pos_min
        )
        pos_max_parsed = (
            _parse_datetime_bound(pos_max) if pos_is_orderable else pos_max
        )

        if pos_is_orderable:
            pos_mask = (position_data >= pos_min_parsed) & (
                position_data <= pos_max_parsed
            )
        else:
            pos_indices = np.arange(len(position_data))
            pos_mask = (pos_max > pos_indices - 0.5) & (
                pos_min < pos_indices + 0.5
            )

        selected_indices = np.where(pos_mask)[0]

        for i in selected_indices:
            if not _bar_value_in_selection_range(
                trace, i, value_data[i], value_min, value_max
            ):
                continue
            if orientation == "v":
                selected_bars.append(
                    _build_bar_point(
                        trace=trace,
                        trace_idx=trace_idx,
                        point_idx=i,
                        x_value=x_data[i],
                        y_value=value_data[i].item()
                        if hasattr(value_data[i], "item")
                        else value_data[i],
                    )
                )
            else:  # horizontal
                selected_bars.append(
                    _build_bar_point(
                        trace=trace,
                        trace_idx=trace_idx,
                        point_idx=i,
                        x_value=value_data[i].item()
                        if hasattr(value_data[i], "item")
                        else value_data[i],
                        y_value=y_data[i],
                    )
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

        if orientation == "v":
            position_data = x_data
            value_data = y_data
            pos_min, pos_max = x_min, x_max
            value_min, value_max = y_min, y_max
        else:  # orientation == "h"
            position_data = y_data
            value_data = x_data
            pos_min, pos_max = y_min, y_max
            value_min, value_max = x_min, x_max

        for i, pos_val in enumerate(position_data):
            pos_in_range = False

            if _is_orderable_value(pos_val) and _is_orderable_value(pos_min):
                pos_min_p = _parse_datetime_bound(pos_min)
                pos_max_p = _parse_datetime_bound(pos_max)
                pos_in_range = pos_min_p <= pos_val <= pos_max_p
            else:
                bar_min = i - 0.5
                bar_max = i + 0.5
                pos_in_range = not (pos_max <= bar_min or pos_min >= bar_max)

            if not pos_in_range:
                continue
            if not _bar_value_in_selection_range(
                trace, i, value_data[i], value_min, value_max
            ):
                continue

            if orientation == "v":
                selected_bars.append(
                    _build_bar_point(
                        trace=trace,
                        trace_idx=trace_idx,
                        point_idx=i,
                        x_value=x_data[i],
                        y_value=value_data[i],
                    )
                )
            else:  # horizontal
                selected_bars.append(
                    _build_bar_point(
                        trace=trace,
                        trace_idx=trace_idx,
                        point_idx=i,
                        x_value=value_data[i],
                        y_value=y_data[i],
                    )
                )

    return selected_bars


def _get_selection_point_id(
    point: dict[str, Any],
) -> tuple[int, int] | None:
    import numbers

    curve_number = point.get("curveNumber")
    point_index = point.get("pointIndex", point.get("pointNumber"))

    if isinstance(curve_number, numbers.Integral) and isinstance(
        point_index, numbers.Integral
    ):
        return (int(curve_number), int(point_index))
    return None


def _bar_value_in_selection_range(
    trace: Any,
    point_idx: int,
    point_value: Any,
    selection_min: Any,
    selection_max: Any,
) -> bool:
    base = _get_indexed_value(getattr(trace, "base", None), point_idx)
    if base is None:
        base = 0

    lower = min(base, point_value)
    upper = max(base, point_value)
    return not (selection_max < lower or selection_min > upper)


def _build_bar_point(
    trace: Any,
    trace_idx: int,
    point_idx: int,
    x_value: Any,
    y_value: Any,
) -> dict[str, Any]:
    point: dict[str, Any] = {
        "x": x_value,
        "y": y_value,
        "curveNumber": trace_idx,
        "pointIndex": int(point_idx),
        "pointNumber": int(point_idx),
    }

    name = getattr(trace, "name", None)
    if name:
        point["name"] = name

    customdata = _get_indexed_value(
        getattr(trace, "customdata", None), point_idx
    )
    if customdata is not None:
        point["customdata"] = customdata

    text = _get_indexed_value(getattr(trace, "text", None), point_idx)
    if text is not None:
        point["text"] = text

    hovertext = _get_indexed_value(
        getattr(trace, "hovertext", None), point_idx
    )
    if hovertext is not None:
        point["hovertext"] = hovertext

    return point


def _append_map_scatter_points_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Extract points from map scatter traces (scattermap, scattermapbox, scattergeo).

    These traces use lat/lon instead of x/y. If the frontend already sent
    points with lat/lon, we preserve them. Otherwise, we extract from trace data.
    """
    existing_points = [p for p in selection_data.get("points", []) if p]
    indices = selection_data.get("indices", [])

    # If frontend already sent lat/lon points, nothing to do
    if existing_points and any(
        "lat" in p or "lon" in p for p in existing_points
    ):
        return

    # Extract points from trace data using indices
    if not indices or existing_points:
        return

    map_types = ("scattermap", "scattermapbox", "scattergeo")
    extracted: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) not in map_types:
            continue

        lat_data = getattr(trace, "lat", None)
        lon_data = getattr(trace, "lon", None)
        if lat_data is None or lon_data is None:
            continue

        for idx in indices:
            if not (0 <= idx < len(lat_data)):
                continue

            point: dict[str, Any] = {
                "lat": lat_data[idx],
                "lon": lon_data[idx],
                "pointIndex": idx,
                "curveNumber": trace_idx,
            }

            # Add optional fields
            customdata = getattr(trace, "customdata", None)
            if customdata is not None and idx < len(customdata):
                point["customdata"] = customdata[idx]

            text = getattr(trace, "text", None)
            if text is not None:
                point["text"] = text if isinstance(text, str) else text[idx]

            hovertext = getattr(trace, "hovertext", None)
            if hovertext is not None:
                point["hovertext"] = (
                    hovertext if isinstance(hovertext, str) else hovertext[idx]
                )

            name = getattr(trace, "name", None)
            if name:
                point["name"] = name

            extracted.append(point)

    if extracted:
        selection_data["points"] = extracted
