# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import numbers
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
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
    from collections.abc import Callable

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
#   "lasso": {
#     "x": [...],
#     "y": [...],
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


def _to_numeric_coord(value: Any) -> float | None:
    """Convert a numeric/datetime-like value to a float for geometry tests."""
    import datetime

    def _to_utc_timestamp(dt: datetime.datetime) -> float:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.timestamp()

    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime.datetime):
        return _to_utc_timestamp(value)
    if isinstance(value, datetime.date):
        return _to_utc_timestamp(
            datetime.datetime.combine(
                value,
                datetime.time(),
                tzinfo=datetime.timezone.utc,
            )
        )
    if isinstance(value, str):
        parsed = _parse_datetime_bound(value)
        if isinstance(parsed, datetime.datetime):
            return _to_utc_timestamp(parsed)
        if isinstance(parsed, datetime.date):
            return _to_utc_timestamp(
                datetime.datetime.combine(
                    parsed,
                    datetime.time(),
                    tzinfo=datetime.timezone.utc,
                )
            )
    return None


def _category_position_map(values: Any) -> dict[Any, float]:
    """Map categorical axis values to their first-seen axis positions."""
    positions: dict[Any, float] = {}
    next_position = 0.0

    for value in values:
        try:
            if value not in positions:
                positions[value] = next_position
                next_position += 1.0
        except TypeError:
            continue

    return positions


def _safe_category_get(
    positions: dict[Any, float], value: Any, default: float
) -> float:
    """Get a category position, returning default for unhashable values."""
    try:
        return positions.get(value, default)
    except TypeError:
        return default


@mddoc
class plotly(UIElement[PlotlySelection, list[dict[str, Any]]]):
    """Make reactive plots with Plotly.

    Use `mo.ui.plotly` to make plotly plots reactive: select data with your
    cursor on the frontend, get them as a list of dicts in Python!

    This function supports scatter plots, scattergl plots, line charts, area
    charts, bar charts, box plots, violin plots, strip charts, histograms,
    funnel charts, funnelarea charts, waterfall charts, treemap charts,
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
        config: dict[str, Any] | None = None,
        renderer_name: str | None = None,
        *,
        label: str = "",
        on_change: Callable[[JSONType], None] | None = None,
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
                    "box",
                    "violin",
                    "funnel",
                    "funnelarea",
                    "heatmap",
                    "bar",
                    "histogram",
                    "waterfall",
                ):
                    continue
                x_data = getattr(trace, "x", None)
                y_data = getattr(trace, "y", None)
                if x_data is None or y_data is None:
                    continue
                for point_idx, (x, y) in enumerate(
                    zip(x_data, y_data, strict=False)
                ):
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

            # For histograms, pre-compute sample rows using the selection range.
            # Interactive events use bin payloads (pointNumbers) for extraction;
            # programmatic initial selections via add_selection only have a range,
            # so we resolve sample rows here before _convert_value is called.
            has_histogram = any(
                getattr(trace, "type", None) == "histogram"
                for trace in figure.data
            )
            if has_histogram and initial_value.get("range"):
                histogram_points = _extract_histogram_points_from_range(
                    figure, cast(dict[str, Any], initial_value["range"])
                )
                seen = {
                    (p.get("pointIndex"), p.get("curveNumber"))
                    for p in selected_points
                }
                for point in histogram_points:
                    key = (point.get("pointIndex"), point.get("curveNumber"))
                    if key not in seen:
                        seen.add(key)
                        selected_points.append(point)
                        if isinstance(point.get("pointIndex"), int):
                            selected_indices.append(
                                cast(int, point["pointIndex"])
                            )
                initial_value["points"] = selected_points
                initial_value["indices"] = selected_indices

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

        has_waterfall = any(
            getattr(trace, "type", None) == "waterfall"
            for trace in self._figure.data
        )

        # For waterfall charts: extract bars within a range selection or pass
        # through click data.  Waterfall bars stack, so extraction uses
        # cumulative-sum positions rather than raw trace.y values.
        if has_waterfall:
            _append_waterfall_bars_to_selection(
                self._figure, self._selection_data
            )

        has_funnel = any(
            getattr(trace, "type", None) == "funnel"
            for trace in self._figure.data
        )

        # For funnel charts, extract stages that fall within a range selection
        # or pass through click data supplied by the frontend.
        if has_funnel:
            _append_funnel_points_to_selection(
                self._figure, self._selection_data
            )

        has_funnelarea = any(
            getattr(trace, "type", None) == "funnelarea"
            for trace in self._figure.data
        )

        # For funnelarea, pass through the click data from the frontend.
        if has_funnelarea:
            _append_funnelarea_points_to_selection(self._selection_data)

        # For line/scatter charts, extract points from box/lasso selections.
        # Plotly may not send point data for pure line charts, so we extract manually.
        if has_scatter and (value.get("range") or value.get("lasso")):
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

        has_box = any(
            getattr(trace, "type", None) == "box"
            for trace in self._figure.data
        )

        # For box plots (including strip charts which use go.Box traces),
        # expand click pointNumbers and range selections into individual sample rows.
        if has_box:
            _append_box_points_to_selection(self._figure, self._selection_data)

        has_violin = any(
            getattr(trace, "type", None) == "violin"
            for trace in self._figure.data
        )

        # For violin plots, expand click pointNumbers and range selections
        # into individual sample rows.
        if has_violin:
            _append_violin_points_to_selection(
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
    """Append scatter/scattergl/line points from range/lasso to selection data.

    This modifies selection_data in place, appending any scatter/scattergl/line points
    that fall within the active selection shape to the existing points and indices.
    """
    range_value = selection_data.get("range")
    lasso_value = selection_data.get("lasso")

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
        and not _trace_needs_scatter_range_fallback(figure.data[curve_number])
    }
    if (
        existing_points
        and not explicit_curve_numbers
        and not any("curveNumber" in point for point in existing_points)
        and len(scatter_trace_indices) == 1
        and not _trace_needs_scatter_range_fallback(
            figure.data[scatter_trace_indices[0]]
        )
    ):
        explicit_curve_numbers.add(scatter_trace_indices[0])

    def trace_filter(trace_idx: int, trace: Any) -> bool:
        return (
            trace_idx not in explicit_curve_numbers
            and _trace_needs_scatter_range_fallback(trace)
        )

    scatter_points: list[dict[str, Any]] = []
    if isinstance(range_value, dict):
        scatter_points = _extract_scatter_points_from_range(
            figure,
            cast(dict[str, Any], range_value),
            trace_filter=trace_filter,
        )
    elif isinstance(lasso_value, dict):
        scatter_points = _extract_scatter_points_from_lasso(
            figure,
            cast(dict[str, Any], lasso_value),
            trace_filter=trace_filter,
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
    fill = getattr(trace, "fill", None)
    stackgroup = getattr(trace, "stackgroup", None)

    # Filled/stacked scatter traces behave like area charts and still need
    # manual extraction when a selection shape is drawn.
    if fill not in (None, "none") or stackgroup:
        return True

    # Unspecified mode should defer to Plotly's native point payload instead of
    # forcing line-style fallback extraction.
    if mode is None:
        return False

    return not (isinstance(mode, str) and "markers" in mode)


def _extract_scatter_points_from_range(
    figure: go.Figure,
    range_data: dict[str, Any],
    trace_filter: Callable[[int, Any], bool] | None = None,
) -> list[dict[str, Any]]:
    """Extract scatter/scattergl/line points in a selection range.

    Returns points whose x and y both fall inside the selected box.
    """
    if not range_data.get("x"):
        return []

    x_range = range_data["x"]
    x_min, x_max = min(x_range), max(x_range)

    y_min: Any = None
    y_max: Any = None
    y_range = range_data.get("y")
    if isinstance(y_range, list) and y_range:
        y_min, y_max = min(y_range), max(y_range)

    # Use numpy fast path if available for better performance
    if DependencyManager.numpy.has():
        return _extract_scatter_points_numpy(
            figure,
            x_min,
            x_max,
            y_min=y_min,
            y_max=y_max,
            trace_filter=trace_filter,
        )

    return _extract_scatter_points_fallback(
        figure,
        x_min,
        x_max,
        y_min=y_min,
        y_max=y_max,
        trace_filter=trace_filter,
    )


def _extract_scatter_points_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: Any = None,
    y_max: Any = None,
    trace_filter: Callable[[int, Any], bool] | None = None,
) -> list[dict[str, Any]]:
    """Extract scatter/scattergl/line points from selection bounds using numpy."""
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
        has_y_range = y_min is not None and y_max is not None
        y_is_orderable = has_y_range and _is_orderable_axis(y_arr, y_min)

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

        # Filter by x-range
        if x_is_orderable:
            x_mask = (x_arr >= x_min_parsed) & (x_arr <= x_max_parsed)
        else:
            # Categorical: compare against axis category positions, not point
            # indices, so repeated categories map to the same coordinate.
            x_category_positions = _category_position_map(x_data)
            x_positions = np.asarray(
                [
                    _safe_category_get(x_category_positions, value, np.nan)
                    for value in x_data
                ],
                dtype=float,
            )
            x_mask = (x_max > x_positions - 0.5) & (x_min < x_positions + 0.5)

        # Filter by y-range when present
        if has_y_range:
            if y_is_orderable:
                y_mask = (y_arr >= y_min_parsed) & (y_arr <= y_max_parsed)
            else:
                y_category_positions = _category_position_map(y_data)
                y_positions = np.asarray(
                    [
                        _safe_category_get(y_category_positions, value, np.nan)
                        for value in y_data
                    ],
                    dtype=float,
                )
                y_mask = (y_max > y_positions - 0.5) & (
                    y_min < y_positions + 0.5
                )
            in_box_mask = x_mask & y_mask
        else:
            in_box_mask = x_mask

        selected_indices = set(np.where(in_box_mask)[0].tolist())

        # Build point dicts for selected indices
        for idx in sorted(selected_indices):
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
    y_min: Any = None,
    y_max: Any = None,
    trace_filter: Callable[[int, Any], bool] | None = None,
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

        has_y_range = y_min is not None and y_max is not None
        selected_indices: set[int] = set()
        x_min_p = _parse_datetime_bound(x_min)
        x_max_p = _parse_datetime_bound(x_max)
        y_min_p = _parse_datetime_bound(y_min) if has_y_range else None
        y_max_p = _parse_datetime_bound(y_max) if has_y_range else None

        x_category_positions = _category_position_map(x_data)
        y_category_positions = _category_position_map(y_data)

        # First pass: include points directly inside current selection bounds.
        for point_idx, (x_val, y_val) in enumerate(
            zip(x_data, y_data, strict=False)
        ):
            x_in_range = False

            if _is_orderable_value(x_val) and _is_orderable_value(x_min):
                x_in_range = x_min_p <= x_val <= x_max_p
            else:
                # TypeError can occur when x_val is unhashable (e.g. a list or
                # dict), which dict.get() cannot accept as a key.
                try:
                    x_position = x_category_positions.get(x_val)
                except TypeError:
                    continue
                if x_position is None:
                    continue
                cell_x_min = x_position - 0.5
                cell_x_max = x_position + 0.5
                x_in_range = not (x_max <= cell_x_min or x_min >= cell_x_max)

            y_in_range = True
            if has_y_range:
                if _is_orderable_value(y_val) and _is_orderable_value(y_min):
                    y_in_range = (
                        cast(Any, y_min_p) <= y_val <= cast(Any, y_max_p)
                    )
                else:
                    # TypeError can occur when y_val is unhashable (e.g. a list or
                    # dict), which dict.get() cannot accept as a key.
                    try:
                        y_position = y_category_positions.get(y_val)
                    except TypeError:
                        continue
                    if y_position is None:
                        continue
                    cell_y_min = y_position - 0.5
                    cell_y_max = y_position + 0.5
                    y_in_range = not (
                        y_max <= cell_y_min or y_min >= cell_y_max
                    )

            if x_in_range and y_in_range:
                selected_indices.add(point_idx)

        for point_idx in sorted(selected_indices):
            x_val = x_data[point_idx]
            y_val = y_data[point_idx]
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


def _point_on_segment(
    x: float, y: float, x1: float, y1: float, x2: float, y2: float
) -> bool:
    """Return True when (x, y) lies on the segment [(x1, y1), (x2, y2)]."""
    tolerance = 1e-9
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > tolerance:
        return False

    dot = (x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)
    if dot < -tolerance:
        return False

    segment_length_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
    return dot <= segment_length_sq + tolerance


def _point_in_polygon(
    x: float, y: float, polygon_x: list[float], polygon_y: list[float]
) -> bool:
    """Return True when point is inside or on boundary of polygon."""
    if len(polygon_x) < 3 or len(polygon_x) != len(polygon_y):
        return False

    for idx in range(len(polygon_x)):
        nxt = (idx + 1) % len(polygon_x)
        if _point_on_segment(
            x,
            y,
            polygon_x[idx],
            polygon_y[idx],
            polygon_x[nxt],
            polygon_y[nxt],
        ):
            return True

    inside = False
    prev = len(polygon_x) - 1
    for idx in range(len(polygon_x)):
        xi = polygon_x[idx]
        yi = polygon_y[idx]
        xj = polygon_x[prev]
        yj = polygon_y[prev]
        intersects = (yi > y) != (yj > y) and (
            x < ((xj - xi) * (y - yi) / (yj - yi) + xi)
        )
        if intersects:
            inside = not inside
        prev = idx
    return inside


def _extract_scatter_points_from_lasso(
    figure: go.Figure,
    lasso_data: dict[str, Any],
    trace_filter: Callable[[int, Any], bool] | None = None,
) -> list[dict[str, Any]]:
    """Extract scatter/scattergl/line points that fall inside a lasso polygon."""
    lasso_x = lasso_data.get("x")
    lasso_y = lasso_data.get("y")
    if (
        not isinstance(lasso_x, list)
        or not isinstance(lasso_y, list)
        or len(lasso_x) < 3
        or len(lasso_x) != len(lasso_y)
    ):
        return []

    selected_points: list[dict[str, Any]] = []

    x_axes: list[go.layout.XAxis] = []
    figure.for_each_xaxis(x_axes.append)
    x_axis = x_axes[0] if len(x_axes) == 1 else None

    y_axes: list[go.layout.YAxis] = []
    figure.for_each_yaxis(y_axes.append)
    y_axis = y_axes[0] if len(y_axes) == 1 else None

    x_field = x_axis.title.text if (x_axis and x_axis.title.text) else "x"
    y_field = y_axis.title.text if (y_axis and y_axis.title.text) else "y"

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) not in {"scatter", "scattergl"}:
            continue
        if trace_filter is not None and not trace_filter(trace_idx, trace):
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        if x_data is None or y_data is None:
            continue

        # Use the same categorical coordinate mapping as box/range selection so
        # lasso geometry is consistent with point-in-range checks.
        x_category_to_index: dict[Any, float] = _category_position_map(x_data)
        y_category_to_index: dict[Any, float] = _category_position_map(y_data)

        polygon_x: list[float] = []
        polygon_y: list[float] = []
        for raw_x, raw_y in zip(lasso_x, lasso_y, strict=False):
            x_coord = _to_numeric_coord(raw_x)
            if x_coord is None:
                x_coord = _safe_category_get(x_category_to_index, raw_x, -1)
                if x_coord == -1:
                    x_coord = None

            y_coord = _to_numeric_coord(raw_y)
            if y_coord is None:
                y_coord = _safe_category_get(y_category_to_index, raw_y, -1)
                if y_coord == -1:
                    y_coord = None

            if x_coord is None or y_coord is None:
                polygon_x = []
                polygon_y = []
                break

            polygon_x.append(x_coord)
            polygon_y.append(y_coord)

        if not polygon_x:
            continue

        for point_idx, (x_val, y_val) in enumerate(
            zip(x_data, y_data, strict=False)
        ):
            x_coord = _to_numeric_coord(x_val)
            if x_coord is None:
                try:
                    x_coord = x_category_to_index.get(x_val)
                except TypeError:
                    x_coord = None

            y_coord = _to_numeric_coord(y_val)
            if y_coord is None:
                try:
                    y_coord = y_category_to_index.get(y_val)
                except TypeError:
                    y_coord = None

            if x_coord is None or y_coord is None:
                continue

            if _point_in_polygon(x_coord, y_coord, polygon_x, polygon_y):
                point_dict = {
                    x_field: x_val,
                    y_field: y_val,
                    "curveNumber": trace_idx,
                    "pointIndex": point_idx,
                }
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
    converts selected bin payloads (pointNumbers) to underlying sample rows so
    .value behaves like row-level selections from scatter plots.

    Pre-computed sample rows from fig.add_selection() have no pointNumbers and
    are passed through the filter unchanged — they do not need re-expansion.
    """
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    histogram_curve_numbers = {
        trace_idx
        for trace_idx, trace in enumerate(figure.data)
        if getattr(trace, "type", None) == "histogram"
    }
    if not histogram_curve_numbers:
        return

    # Expand bin payloads (those with pointNumbers) into sample rows.
    # Points without pointNumbers are pre-computed sample rows (e.g. from
    # add_selection) and are preserved through the filter step below.
    histogram_points = _extract_histogram_points_from_bins(figure, all_points)

    # Drop only bin-level payloads (those with pointNumbers); keep sample rows
    # from other traces and pre-computed histogram rows (e.g. add_selection).
    filtered_points: list[dict[str, Any]] = []
    filtered_indices: list[int] = []
    seen = set()

    for point_idx, point in enumerate(all_points):
        if not point:
            continue

        curve_number = point.get("curveNumber")
        if curve_number in histogram_curve_numbers and "pointNumbers" in point:
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

    # Merge bin-expanded sample rows with deduplication by (curveNumber, pointIndex).
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
) -> dict[str, Any] | None:
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
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    has_real_points = any(all_points)
    if not has_real_points and not bar_items:
        # Ensure empty-dict placeholders from the frontend do not leak through
        selection_data["points"] = []
        selection_data["indices"] = []
        return

    seen: set[tuple[int, int]] = set()
    merged_points: list[dict[str, Any]] = []
    merged_indices: list[int] = []

    for point_idx, point in enumerate(all_points):
        if not point:
            continue

        point_id = _get_selection_point_id(point)
        if point_id is not None:
            if point_id in seen:
                continue
            seen.add(point_id)
        merged_points.append(point)
        if point_idx < len(all_indices) and isinstance(
            all_indices[point_idx], int
        ):
            merged_indices.append(all_indices[point_idx])
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

        # For vertical bars: filter by x-axis position
        # For horizontal bars: filter by y-axis position (swap roles)
        if orientation == "v":
            # Vertical bars: x-axis determines which bars are selected
            # y-axis is the value (we don't filter by it, similar to Altair)
            position_data = x_arr
            value_data = y_arr
            pos_min, pos_max = x_min, x_max
            value_min, value_max = y_min, y_max
        else:  # orientation == "h"
            # Horizontal bars: y-axis determines which bars are selected
            # x-axis is the value
            position_data = y_arr
            value_data = x_arr
            pos_min, pos_max = y_min, y_max
            value_min, value_max = x_min, x_max

        # Determine if position axis is orderable (numeric or datetime-like)
        pos_is_orderable = _is_orderable_axis(position_data, pos_min)

        # Parse datetime bounds (frontend sends ISO strings via JSON)
        pos_min_parsed = (
            _parse_datetime_bound(pos_min) if pos_is_orderable else pos_min
        )
        pos_max_parsed = (
            _parse_datetime_bound(pos_max) if pos_is_orderable else pos_max
        )

        # Compute mask for valid indices
        if pos_is_orderable:
            # Orderable axis: direct range comparison
            # TODO: Consider bar width in future implementations
            # Currently treating bars as points at their position value
            pos_mask = (position_data >= pos_min_parsed) & (
                position_data <= pos_max_parsed
            )
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

        # For vertical bars: filter by x-axis position
        # For horizontal bars: filter by y-axis position
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

        # Iterate through bars
        for i, pos_val in enumerate(position_data):
            # Check if bar position is within selection range
            pos_in_range = False

            if _is_orderable_value(pos_val) and _is_orderable_value(pos_min):
                # Orderable axis (numeric or datetime): direct comparison
                # Parse datetime bounds (frontend sends ISO strings)
                pos_min_p = _parse_datetime_bound(pos_min)
                pos_max_p = _parse_datetime_bound(pos_max)
                # TODO: Consider bar width in future implementations
                # Currently treating bars as points at their position value
                pos_in_range = pos_min_p <= pos_val <= pos_max_p
            else:
                # Categorical axis: each bar spans (index - 0.5) to (index + 0.5)
                # Include bar if selection range strictly overlaps with bar bounds
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
    curve_number = point.get("curveNumber")
    point_index = point.get("pointIndex", point.get("pointNumber"))

    if isinstance(curve_number, numbers.Integral) and isinstance(
        point_index, numbers.Integral
    ):
        return (int(curve_number), int(point_index))
    return None


def _bar_value_in_selection_range(
    trace: object,
    point_idx: int,
    point_value: object,
    selection_min: object,
    selection_max: object,
) -> bool:
    base = _get_indexed_value(getattr(trace, "base", None), point_idx)
    if base is None:
        base = 0

    numeric_base = _to_numeric_bar_value(base)
    numeric_point_value = _to_numeric_bar_value(point_value)
    numeric_selection_min = _to_numeric_bar_value(selection_min)
    numeric_selection_max = _to_numeric_bar_value(selection_max)

    if (
        numeric_base is None
        or numeric_point_value is None
        or numeric_selection_min is None
        or numeric_selection_max is None
    ):
        return False

    lower = min(numeric_base, numeric_point_value)
    upper = max(numeric_base, numeric_point_value)
    return not (numeric_selection_max < lower or numeric_selection_min > upper)


def _to_numeric_bar_value(value: object) -> float | None:
    if hasattr(value, "item"):
        value = value.item()

    if isinstance(value, bool):
        return None

    if isinstance(value, numbers.Real):
        return float(value)

    return None


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

    for field in ("customdata", "text", "hovertext"):
        val = _get_indexed_value(getattr(trace, field, None), point_idx)
        if val is not None:
            point[field] = val

    return point


def _compute_waterfall_bar_extents(
    y_data: Any,
    measures: Any,
    base: float,
) -> list[tuple[float, float]]:
    """Return the visual (low, high) extent for each waterfall bar.

    Waterfall bars stack on top of each other, so the visual position of
    each bar depends on the cumulative sum of preceding relative bars:

    * ``"absolute"`` — bar runs from *base* to y[i]; resets running total.
    * ``"relative"`` — bar runs from running_total to running_total + y[i].
    * ``"total"``    — bar runs from *base* to running_total (display only;
      does not alter the running total).
    """
    running_total = base
    extents: list[tuple[float, float]] = []

    default_measure = "relative"
    for i, y_val in enumerate(y_data):
        try:
            m = (
                str(measures[i]).lower()
                if measures is not None and i < len(measures)
                else default_measure
            )
        except (IndexError, TypeError):
            m = default_measure

        try:
            v = float(y_val)
        except (TypeError, ValueError):
            v = 0.0

        if m == "absolute":
            bar_lo, bar_hi = base, v
            running_total = v
        elif m == "total":
            bar_lo, bar_hi = base, running_total
        else:  # relative
            bar_lo = running_total
            bar_hi = running_total + v
            running_total = bar_hi

        extents.append((min(bar_lo, bar_hi), max(bar_lo, bar_hi)))

    return extents


def _append_waterfall_bars_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Handle selection data for go.Waterfall traces.

    Two cases:
    1. Range selection (dragmode="select"): extract waterfall bars whose
       visual extent (accounting for stacking) overlaps the selection rectangle.
    2. Click selection: pass through frontend-supplied points, stripping
       empty-dict placeholders and re-syncing indices.
    """
    range_value = selection_data.get("range")
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    if isinstance(range_value, dict):
        waterfall_items = _extract_waterfall_bars_from_range(
            figure, cast(dict[str, Any], range_value)
        )
        has_real_points = any(all_points)
        if not has_real_points and not waterfall_items:
            selection_data["points"] = []
            selection_data["indices"] = []
            return

        seen: set[tuple[int, int]] = set()
        merged_points: list[dict[str, Any]] = []
        merged_indices: list[int] = []

        for point_idx, point in enumerate(all_points):
            if not point:
                continue
            point_id = _get_selection_point_id(point)
            if point_id is not None:
                if point_id in seen:
                    continue
                seen.add(point_id)
            merged_points.append(point)
            if point_idx < len(all_indices) and isinstance(
                all_indices[point_idx], int
            ):
                merged_indices.append(all_indices[point_idx])
            elif point_id is not None:
                merged_indices.append(point_id[1])

        for point in waterfall_items:
            point_id = _get_selection_point_id(point)
            if point_id is not None:
                if point_id in seen:
                    continue
                seen.add(point_id)
                merged_indices.append(point_id[1])
            merged_points.append(point)

        selection_data["points"] = merged_points
        selection_data["indices"] = merged_indices
    else:
        # Click: strip empty placeholders, re-sync indices.
        clean_points = [p for p in all_points if p]
        if not clean_points:
            selection_data["points"] = []
            selection_data["indices"] = []
            return
        incoming_index_map = {
            id(p): idx
            for idx, p in zip(all_indices, all_points, strict=False)
            if p and isinstance(idx, int)
        }
        clean_indices: list[int] = []
        for p in clean_points:
            idx = incoming_index_map.get(id(p))
            if isinstance(idx, int):
                clean_indices.append(idx)
            else:
                pi = p.get("pointIndex", p.get("pointNumber"))
                if isinstance(pi, int):
                    clean_indices.append(pi)
        selection_data["points"] = clean_points
        selection_data["indices"] = clean_indices


def _extract_waterfall_bars_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Dispatch to numpy or fallback waterfall extraction."""
    if not range_data.get("x") or not range_data.get("y"):
        return []

    x_range = range_data["x"]
    y_range = range_data["y"]
    x_min, x_max = min(x_range), max(x_range)
    y_min, y_max = min(y_range), max(y_range)

    if DependencyManager.numpy.has():
        return _extract_waterfall_bars_numpy(
            figure, x_min, x_max, y_min, y_max
        )
    return _extract_waterfall_bars_fallback(figure, x_min, x_max, y_min, y_max)


def _extract_waterfall_bars_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract waterfall bars using numpy for vectorized filtering."""
    import numpy as np

    selected: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "waterfall":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        if x_data is None or y_data is None:
            continue

        n = len(y_data) if hasattr(y_data, "__len__") else 0
        if n == 0:
            continue

        orientation = getattr(trace, "orientation", None) or "v"
        measures = getattr(trace, "measure", None)
        trace_base = getattr(trace, "base", None)
        base = (
            float(trace_base) if isinstance(trace_base, (int, float)) else 0.0
        )

        if orientation == "h":
            # Horizontal: y=labels (categorical), x=values (stacking)
            cat_data, val_data = y_data, x_data
            cat_min, cat_max = y_min, y_max
            val_min, val_max = x_min, x_max
        else:
            # Vertical (default): x=labels (categorical), y=values (stacking)
            cat_data, val_data = x_data, y_data
            cat_min, cat_max = x_min, x_max
            val_min, val_max = y_min, y_max

        # Category axis: orderable (numeric/datetime) or positional (categorical)
        cat_arr = np.asarray(cat_data)
        cat_is_orderable = _is_orderable_axis(cat_arr, cat_min)
        if cat_is_orderable:
            cat_min_p = _parse_datetime_bound(cat_min)
            cat_max_p = _parse_datetime_bound(cat_max)
            cat_mask = (cat_arr >= cat_min_p) & (cat_arr <= cat_max_p)
        else:
            cat_positions = np.arange(n, dtype=np.float64)
            cat_mask = (cat_max > cat_positions - 0.5) & (
                cat_min < cat_positions + 0.5
            )

        # Value axis: use stacked extents (low, high) for each bar
        extents = _compute_waterfall_bar_extents(val_data, measures, base)
        ext_arr = np.array(extents, dtype=np.float64)  # shape (n, 2)
        bar_lo = ext_arr[:, 0]
        bar_hi = ext_arr[:, 1]
        # Overlap condition: val_min < bar_hi AND val_max > bar_lo
        val_mask = (val_min < bar_hi) & (val_max > bar_lo)

        mask = cat_mask & val_mask
        for i in np.where(mask)[0]:
            selected.append(
                _build_waterfall_point(
                    trace, trace_idx, int(i), x_data, y_data, measures
                )
            )

    return selected


def _extract_waterfall_bars_fallback(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract waterfall bars using pure Python (fallback when numpy unavailable)."""
    selected: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "waterfall":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        if x_data is None or y_data is None:
            continue

        n = len(y_data) if hasattr(y_data, "__len__") else 0
        if n == 0:
            continue

        orientation = getattr(trace, "orientation", None) or "v"
        measures = getattr(trace, "measure", None)
        trace_base = getattr(trace, "base", None)
        base = (
            float(trace_base) if isinstance(trace_base, (int, float)) else 0.0
        )

        if orientation == "h":
            cat_data, val_data = y_data, x_data
            cat_min, cat_max = y_min, y_max
            val_min, val_max = x_min, x_max
        else:
            cat_data, val_data = x_data, y_data
            cat_min, cat_max = x_min, x_max
            val_min, val_max = y_min, y_max

        extents = _compute_waterfall_bar_extents(val_data, measures, base)

        for i, (bar_lo, bar_hi) in enumerate(extents):
            # Category check: orderable (numeric/datetime) or positional
            cat_val = _get_indexed_value(cat_data, i)
            if _is_orderable_value(cat_val) and _is_orderable_value(cat_min):
                cat_min_p = _parse_datetime_bound(cat_min)
                cat_max_p = _parse_datetime_bound(cat_max)
                cat_val_p = _parse_datetime_bound(cat_val)
                if not (cat_min_p <= cat_val_p <= cat_max_p):
                    continue
            else:
                if cat_max <= i - 0.5 or cat_min >= i + 0.5:
                    continue
            # Value check: bar [bar_lo, bar_hi] overlaps [val_min, val_max]
            if val_min >= bar_hi or val_max <= bar_lo:
                continue
            selected.append(
                _build_waterfall_point(
                    trace, trace_idx, i, x_data, y_data, measures
                )
            )

    return selected


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


def _append_violin_points_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Expand violin plot selections into individual underlying data points.

    Handles three cases:
    - Range/lasso with individual points already sent by Plotly (``points``
      enabled): Plotly already delivered the right individual data points via
      the ``onSelected`` event; pass them through unchanged.
    - Range/lasso without individual points (``points`` disabled): extract
      all underlying sample rows whose category position overlaps the selection
      range from the figure data.
    - Click events (no range/lasso): the frontend sends ``pointNumbers`` for
      the clicked violin element; expand these into one dict per sample row so
      Python callers get row-level data.
    """
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    violin_curve_numbers = {
        trace_idx
        for trace_idx, trace in enumerate(figure.data)
        if getattr(trace, "type", None) == "violin"
    }
    if not violin_curve_numbers:
        return

    range_value = selection_data.get("range")
    lasso_value = selection_data.get("lasso")

    # --- Range/lasso selection path (onSelected event) ---
    if isinstance(range_value, dict) or isinstance(lasso_value, dict):
        existing_violin = [
            p
            for p in all_points
            if p and p.get("curveNumber") in violin_curve_numbers
        ]
        existing_non_violin = [
            p
            for p in all_points
            if p and p.get("curveNumber") not in violin_curve_numbers
        ]
        existing_non_violin_indices = [
            idx
            for idx, p in zip(all_indices, all_points, strict=False)
            if p and p.get("curveNumber") not in violin_curve_numbers
        ]

        if existing_violin:
            # Plotly already sent the individual selected data points because
            # points is enabled.  Use them as-is; do NOT re-extract from the
            # range (which can fail on categorical axes and would discard richer
            # hovertemplate fields like custom ids).
            clean_points = existing_violin + existing_non_violin
            # Preserve incoming indices from the frontend payload rather than
            # recomputing from pointIndex only — Plotly may send pointNumber
            # instead. Map each point object to its original index by identity.
            incoming_index_map = {
                id(p): idx
                for idx, p in zip(all_indices, all_points, strict=False)
                if p
            }
            clean_indices: list[int] = []
            for p in clean_points:
                idx = incoming_index_map.get(id(p))
                if isinstance(idx, int):
                    clean_indices.append(idx)
                else:
                    pid = _get_selection_point_id(p)
                    if pid is not None:
                        clean_indices.append(pid[1])
            selection_data["points"] = clean_points
            selection_data["indices"] = clean_indices
            return

        # No individual points from Plotly → points attribute is disabled.
        # Only extract from a range selection; lasso events without a range
        # dict would pass an empty range_dict and incorrectly select all rows.
        if not isinstance(range_value, dict):
            return
        violin_points = _extract_violin_points_from_range(
            figure, cast(dict[str, Any], range_value)
        )

        if violin_points or existing_non_violin:
            seen: set[tuple[int, int]] = set()
            merged_points: list[dict[str, Any]] = []
            merged_indices: list[int] = []

            for idx, point in zip(
                existing_non_violin_indices, existing_non_violin, strict=False
            ):
                point_id = _get_selection_point_id(point)
                if point_id is not None:
                    if point_id in seen:
                        continue
                    seen.add(point_id)
                merged_points.append(point)
                if isinstance(idx, int):
                    merged_indices.append(idx)

            for point in violin_points:
                point_id = _get_selection_point_id(point)
                if point_id is not None:
                    if point_id in seen:
                        continue
                    seen.add(point_id)
                    merged_indices.append(point_id[1])
                merged_points.append(point)

            selection_data["points"] = merged_points
            selection_data["indices"] = merged_indices
        else:
            # Range didn't overlap any violin category and no non-violin points
            # exist — clear any stale placeholder dicts the frontend may have sent.
            selection_data["points"] = []
            selection_data["indices"] = []
        return

    # --- Click event path ---
    # Violin element clicks include pointNumbers (all raw-data indices in the
    # group).  Expand each such click-point into individual sample rows.
    has_violin_click_with_numbers = any(
        p.get("curveNumber") in violin_curve_numbers and "pointNumbers" in p
        for p in all_points
        if p
    )
    if not has_violin_click_with_numbers:
        return

    expanded_points: list[dict[str, Any]] = []
    expanded_indices: list[int] = []
    seen_ids: set[tuple[int, int]] = set()

    for point in all_points:
        if not point:
            continue

        curve_number = point.get("curveNumber")

        if curve_number not in violin_curve_numbers:
            point_id = _get_selection_point_id(point)
            if point_id is not None and point_id in seen_ids:
                continue
            if point_id is not None:
                seen_ids.add(point_id)
            expanded_points.append(point)
            # Use _get_selection_point_id to capture pointNumber as a fallback
            # when pointIndex is absent (e.g. hovermode-'x' multi-trace clicks).
            if point_id is not None:
                expanded_indices.append(point_id[1])
            elif isinstance(point.get("pointIndex"), int):
                expanded_indices.append(cast(int, point["pointIndex"]))
            continue

        point_numbers = point.get("pointNumbers")
        if not isinstance(point_numbers, list) or not (
            0 <= cast(int, curve_number) < len(figure.data)
        ):
            expanded_points.append(point)
            if isinstance(point.get("pointIndex"), int):
                expanded_indices.append(cast(int, point["pointIndex"]))
            continue

        trace = figure.data[cast(int, curve_number)]
        for raw_idx in point_numbers:
            if not isinstance(raw_idx, int):
                continue
            sample = _build_violin_sample_point(
                trace, cast(int, curve_number), raw_idx
            )
            if sample is None:
                continue
            point_id = _get_selection_point_id(sample)
            if point_id is not None and point_id in seen_ids:
                continue
            if point_id is not None:
                seen_ids.add(point_id)
            expanded_points.append(sample)
            expanded_indices.append(raw_idx)

    selection_data["points"] = expanded_points
    selection_data["indices"] = expanded_indices


def _extract_violin_points_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract violin plot underlying data points that fall within a selection range.

    For each violin trace, both the category axis (x for vertical, y for
    horizontal) and the value axis are compared against the selection range.
    Only sample rows whose category group overlaps the selection *and* whose
    individual value falls within the value-axis bounds are returned.  When the
    value-axis range is absent from ``range_data`` (e.g. a selection spanning
    the full y-axis) all rows in matching categories are included.
    """
    if DependencyManager.numpy.has():
        return _extract_violin_points_numpy(figure, range_data)
    return _extract_violin_points_fallback(figure, range_data)


def _extract_violin_points_numpy(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract violin plot data points from a selection range using numpy.

    Filters by both the category axis (which violin group falls inside the
    selection box) and the value axis (which individual sample values fall
    inside the selection box).  When ``points`` is disabled in the Plotly
    figure, Plotly does not send individual point coordinates, so we derive
    inclusion from the underlying trace arrays.
    """
    import numpy as np

    x_range = range_data.get("x")
    y_range = range_data.get("y")

    selected: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "violin":
            continue

        orientation = getattr(trace, "orientation", "v") or "v"
        if orientation == "h":
            cat_range = y_range
            val_range = x_range
            cat_data = getattr(trace, "y", None)
            val_data = getattr(trace, "x", None)
        else:
            cat_range = x_range
            val_range = y_range
            cat_data = getattr(trace, "x", None)
            val_data = getattr(trace, "y", None)

        if val_data is None:
            continue

        val_arr = np.asarray(val_data)
        n = len(val_arr)
        if n == 0:
            continue

        if cat_data is None:
            cat_arr: list[Any] = [getattr(trace, "name", trace_idx)] * n
        else:
            cat_arr_raw = np.asarray(cat_data)
            if cat_arr_raw.ndim == 0 or len(cat_arr_raw) != n:
                cat_val = (
                    cat_arr_raw.item()
                    if hasattr(cat_arr_raw, "item") and cat_arr_raw.ndim == 0
                    else (cat_arr_raw[0] if len(cat_arr_raw) > 0 else None)
                )
                cat_arr = [cat_val] * n
            else:
                cat_arr = cat_arr_raw.tolist()

        if cat_range:
            cat_min, cat_max = min(cat_range), max(cat_range)
            cat_np = np.asarray(cat_arr)
            cat_is_orderable = _is_orderable_axis(cat_np, cat_min)

            if cat_is_orderable:
                cat_min_p = _parse_datetime_bound(cat_min)
                cat_max_p = _parse_datetime_bound(cat_max)
                cat_mask = np.array(
                    [
                        cat_min_p <= _parse_datetime_bound(v) <= cat_max_p
                        if _is_orderable_value(v)
                        else False
                        for v in cat_arr
                    ]
                )
            else:
                seen_order: dict[Any, float] = {}
                for v in cat_arr:
                    try:
                        if v not in seen_order:
                            seen_order[v] = float(len(seen_order))
                    except TypeError:
                        pass
                positions = np.array(
                    [_safe_category_get(seen_order, v, -1) for v in cat_arr],
                    dtype=np.float64,
                )
                cat_mask = (cat_max > positions - 0.5) & (
                    cat_min < positions + 0.5
                )
        else:
            cat_mask = np.ones(n, dtype=bool)

        if val_range:
            val_min_f = float(min(val_range))
            val_max_f = float(max(val_range))
            try:
                val_numeric = val_arr.astype(float)
                val_mask = (val_numeric >= val_min_f) & (
                    val_numeric <= val_max_f
                )
                cat_mask = cat_mask & val_mask
            except (ValueError, TypeError):
                pass  # non-numeric values; skip value filtering

        selected_indices = np.where(cat_mask)[0]
        for i in selected_indices:
            sample = _build_violin_sample_point(trace, trace_idx, int(i))
            if sample is not None:
                selected.append(sample)

    return selected


def _build_waterfall_point(
    trace: Any,
    trace_idx: int,
    point_idx: int,
    x_data: Any,
    y_data: Any,
    measures: Any,
) -> dict[str, Any]:
    """Build a selection point dict for a single waterfall bar."""
    x_val = _get_indexed_value(x_data, point_idx)
    y_val = _get_indexed_value(y_data, point_idx)
    point: dict[str, Any] = {
        "x": x_val,
        "y": y_val,
        "curveNumber": trace_idx,
        "pointIndex": point_idx,
        "pointNumber": point_idx,
    }
    # Include the measure type so callers know if it's relative/absolute/total
    try:
        m = measures[point_idx] if measures is not None else None
    except (IndexError, TypeError):
        m = None
    if m is not None:
        point["measure"] = str(m)

    name = getattr(trace, "name", None)
    if name:
        point["name"] = name

    for field in ("customdata", "text", "hovertext"):
        val = _get_indexed_value(getattr(trace, field, None), point_idx)
        if val is not None:
            point[field] = val

    return point


def _append_box_points_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Expand box plot selections into individual underlying data points.

    Handles three cases:
    - Range/lasso with individual points already sent by Plotly (``boxpoints``
      enabled): Plotly already delivered the right individual data points via
      the ``onSelected`` event; pass them through unchanged.
    - Range/lasso without individual points (``boxpoints`` disabled): extract
      all underlying sample rows whose category position overlaps the selection
      range from the figure data.
    - Click events (no range/lasso): the frontend sends ``pointNumbers`` for
      the clicked box/whisker element; expand these into one dict per sample
      row so Python callers get row-level data.

    This also handles strip charts (``px.strip()``) which are rendered as
    ``go.Box`` traces with ``boxpoints="all"`` and transparent fills.
    """
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    box_curve_numbers = {
        trace_idx
        for trace_idx, trace in enumerate(figure.data)
        if getattr(trace, "type", None) == "box"
    }
    if not box_curve_numbers:
        return

    range_value = selection_data.get("range")
    lasso_value = selection_data.get("lasso")

    # --- Range/lasso selection path (onSelected event) ---
    if isinstance(range_value, dict) or isinstance(lasso_value, dict):
        # Partition existing points by whether they come from a box trace.
        existing_box = [
            p
            for p in all_points
            if p and p.get("curveNumber") in box_curve_numbers
        ]
        existing_non_box = [
            p
            for p in all_points
            if p and p.get("curveNumber") not in box_curve_numbers
        ]
        existing_non_box_indices = [
            idx
            for idx, p in zip(all_indices, all_points, strict=False)
            if p and p.get("curveNumber") not in box_curve_numbers
        ]

        if existing_box:
            # Plotly already sent the individual selected data points because
            # boxpoints is enabled.  Use them as-is; do NOT re-extract from
            # the range (which can fail on categorical axes and would discard
            # richer hovertemplate fields like sample_id).
            clean_points = existing_box + existing_non_box
            # Preserve incoming indices from the frontend payload rather than
            # recomputing from pointIndex only — Plotly may send pointNumber
            # instead. Map each point object to its original index by identity.
            incoming_index_map = {
                id(p): idx
                for idx, p in zip(all_indices, all_points, strict=False)
                if p
            }
            clean_indices: list[int] = []
            for p in clean_points:
                idx = incoming_index_map.get(id(p))
                if isinstance(idx, int):
                    clean_indices.append(idx)
                else:
                    pid = _get_selection_point_id(p)
                    if pid is not None:
                        clean_indices.append(pid[1])
            selection_data["points"] = clean_points
            selection_data["indices"] = clean_indices
            return

        # No individual points from Plotly → boxpoints is disabled.
        # Only extract from a range selection; lasso events without a range
        # dict would pass an empty range_dict and incorrectly select all rows.
        if not isinstance(range_value, dict):
            return
        box_points = _extract_box_points_from_range(
            figure, cast(dict[str, Any], range_value)
        )

        if box_points or existing_non_box:
            seen: set[tuple[int, int]] = set()
            merged_points: list[dict[str, Any]] = []
            merged_indices: list[int] = []

            for idx, point in zip(
                existing_non_box_indices, existing_non_box, strict=False
            ):
                point_id = _get_selection_point_id(point)
                if point_id is not None:
                    if point_id in seen:
                        continue
                    seen.add(point_id)
                merged_points.append(point)
                if isinstance(idx, int):
                    merged_indices.append(idx)
                elif point_id is not None:
                    merged_indices.append(point_id[1])

            for point in box_points:
                point_id = _get_selection_point_id(point)
                if point_id is not None:
                    if point_id in seen:
                        continue
                    seen.add(point_id)
                    merged_indices.append(point_id[1])
                merged_points.append(point)

            selection_data["points"] = merged_points
            selection_data["indices"] = merged_indices
        else:
            # No box points and no non-box points in range: clear any frontend
            # placeholder dicts that may have leaked into points/indices.
            selection_data["points"] = []
            selection_data["indices"] = []
        return

    # --- Click event path ---
    # Box/whisker clicks include pointNumbers (all raw-data indices in the group).
    # Expand each such click-point into individual sample rows.
    has_box_click_with_numbers = any(
        p.get("curveNumber") in box_curve_numbers and "pointNumbers" in p
        for p in all_points
        if p
    )
    if not has_box_click_with_numbers:
        return

    expanded_points: list[dict[str, Any]] = []
    expanded_indices: list[int] = []
    seen_ids: set[tuple[int, int]] = set()

    for point in all_points:
        if not point:
            continue

        curve_number = point.get("curveNumber")

        # Passthrough non-box points unchanged
        if curve_number not in box_curve_numbers:
            point_id = _get_selection_point_id(point)
            if point_id is not None and point_id in seen_ids:
                continue
            if point_id is not None:
                seen_ids.add(point_id)
                expanded_indices.append(point_id[1])
            expanded_points.append(point)
            continue

        point_numbers = point.get("pointNumbers")
        if not isinstance(point_numbers, list) or not (
            0 <= cast(int, curve_number) < len(figure.data)
        ):
            # No pointNumbers – pass through as-is
            point_id = _get_selection_point_id(point)
            if point_id is not None:
                expanded_indices.append(point_id[1])
            expanded_points.append(point)
            continue

        trace = figure.data[cast(int, curve_number)]
        for raw_idx in point_numbers:
            if not isinstance(raw_idx, int):
                continue
            sample = _build_box_sample_point(
                trace, cast(int, curve_number), raw_idx
            )
            if sample is None:
                continue
            point_id = _get_selection_point_id(sample)
            if point_id is not None and point_id in seen_ids:
                continue
            if point_id is not None:
                seen_ids.add(point_id)
            expanded_points.append(sample)
            expanded_indices.append(raw_idx)

    selection_data["points"] = expanded_points
    selection_data["indices"] = expanded_indices


def _build_global_category_order(
    figure: go.Figure, trace_type: str
) -> dict[Any, float]:
    """Build a category-to-float-position mapping across all traces of the given type.

    Using per-trace first-seen order causes the same category to get different
    numeric positions in different traces (common with Plotly Express faceting/
    coloring).  A single pre-built order from all traces ensures the positions
    are consistent with the axis-global ordering Plotly uses for range values.
    """
    order: dict[Any, float] = {}
    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != trace_type:
            continue
        orientation = getattr(trace, "orientation", "v") or "v"
        cat_data = getattr(trace, "y" if orientation == "h" else "x", None)
        val_data = getattr(trace, "x" if orientation == "h" else "y", None)
        if val_data is None:
            continue
        n = len(val_data) if hasattr(val_data, "__len__") else 0
        if n == 0:
            continue
        if cat_data is None:
            cats: list[Any] = [getattr(trace, "name", None) or trace_idx]
        elif isinstance(cat_data, (str, bytes)):
            cats = [cat_data]
        elif hasattr(cat_data, "__len__") and len(cat_data) == n:
            cats = list(cat_data)
        else:
            try:
                cats = [cat_data[0]]
            except (TypeError, IndexError, KeyError):
                cats = [cat_data]
        for v in cats:
            try:
                if v not in order:
                    order[v] = float(len(order))
            except TypeError:
                pass
    return order


def _extract_box_points_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract box plot underlying data points that fall within a selection range.

    For each box trace the category position (x for vertical, y for horizontal)
    is compared against the selection range.  Only samples whose value coordinate
    also falls within the selection rectangle are returned.
    """
    if DependencyManager.numpy.has():
        return _extract_box_points_numpy(figure, range_data)
    return _extract_box_points_fallback(figure, range_data)


def _extract_box_points_numpy(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract box plot data points from a selection range using numpy."""
    import numpy as np

    x_range = range_data.get("x")
    y_range = range_data.get("y")

    selected: list[dict[str, Any]] = []

    # Build global category order once so that the same category gets the same
    # numeric position across all traces (px faceting can produce traces with
    # different/missing categories, making per-trace first-seen order wrong).
    global_cat_order = _build_global_category_order(figure, "box")

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "box":
            continue

        orientation = getattr(trace, "orientation", "v") or "v"
        # For vertical boxes: x is the category axis, y holds data values.
        # For horizontal boxes: y is the category axis, x holds data values.
        if orientation == "h":
            cat_range = y_range
            val_range = x_range
            cat_data = getattr(trace, "y", None)
            val_data = getattr(trace, "x", None)
        else:
            cat_range = x_range
            val_range = y_range
            cat_data = getattr(trace, "x", None)
            val_data = getattr(trace, "y", None)

        if val_data is None:
            continue

        val_arr = np.asarray(val_data)
        n = len(val_arr)
        if n == 0:
            continue

        # Build per-sample category array.  A box trace can have:
        #   - cat_data as an array (one category per sample, same length as val)
        #   - cat_data as a scalar / None (all samples share one category)
        if cat_data is None:
            # No explicit category; Plotly uses the trace name / index.
            cat_arr: list[Any] = [getattr(trace, "name", trace_idx)] * n
        else:
            cat_arr_raw = np.asarray(cat_data)
            if cat_arr_raw.ndim == 0 or len(cat_arr_raw) != n:
                # Scalar category
                cat_val = (
                    cat_arr_raw.item()
                    if hasattr(cat_arr_raw, "item") and cat_arr_raw.ndim == 0
                    else (cat_arr_raw[0] if len(cat_arr_raw) > 0 else None)
                )
                cat_arr = [cat_val] * n
            else:
                cat_arr = cat_arr_raw.tolist()

        # --- Category filter ---
        if cat_range:
            cat_min, cat_max = min(cat_range), max(cat_range)
            cat_np = np.asarray(cat_arr)
            cat_is_orderable = _is_orderable_axis(cat_np, cat_min)

            if cat_is_orderable:
                cat_min_p = _parse_datetime_bound(cat_min)
                cat_max_p = _parse_datetime_bound(cat_max)
                cat_mask = np.array(
                    [
                        cat_min_p <= _parse_datetime_bound(v) <= cat_max_p
                        if _is_orderable_value(v)
                        else False
                        for v in cat_arr
                    ]
                )
            else:
                # Use the global order so positions are consistent across traces
                positions = np.array(
                    [
                        _safe_category_get(global_cat_order, v, -1)
                        for v in cat_arr
                    ],
                    dtype=np.float64,
                )
                cat_mask = (cat_max > positions - 0.5) & (
                    cat_min < positions + 0.5
                )
        else:
            cat_mask = np.ones(n, dtype=bool)

        # --- Value filter ---
        # Exclude samples whose value coordinate falls outside the selection
        # rectangle (category match alone is insufficient).
        if val_range:
            val_min_p = _parse_datetime_bound(min(val_range))
            val_max_p = _parse_datetime_bound(max(val_range))
            val_mask = np.array(
                [
                    val_min_p <= parsed_v <= val_max_p
                    if _is_orderable_value(parsed_v)
                    else False
                    for parsed_v in (
                        _parse_datetime_bound(v) for v in val_arr.tolist()
                    )
                ]
            )
            cat_mask = cat_mask & val_mask

        selected_indices = np.where(cat_mask)[0]
        for i in selected_indices:
            sample = _build_box_sample_point(trace, trace_idx, int(i))
            if sample is not None:
                selected.append(sample)

    return selected


def _extract_box_points_fallback(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract box plot data points from a selection range (pure Python)."""
    x_range = range_data.get("x")
    y_range = range_data.get("y")

    selected: list[dict[str, Any]] = []

    # Global category order for consistent positions across all box traces
    global_cat_order = _build_global_category_order(figure, "box")

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "box":
            continue

        orientation = getattr(trace, "orientation", "v") or "v"
        if orientation == "h":
            cat_range = y_range
            val_range = x_range
            cat_data = getattr(trace, "y", None)
            val_data = getattr(trace, "x", None)
        else:
            cat_range = x_range
            val_range = y_range
            cat_data = getattr(trace, "x", None)
            val_data = getattr(trace, "y", None)

        if val_data is None:
            continue

        n = len(val_data)
        if n == 0:
            continue

        # Build per-sample category list
        if cat_data is None:
            cat_list: list[Any] = [getattr(trace, "name", trace_idx)] * n
        elif isinstance(cat_data, (str, bytes)):
            cat_list = [cat_data] * n
        elif hasattr(cat_data, "__len__") and len(cat_data) == n:
            cat_list = list(cat_data)
        else:
            try:
                scalar: Any = cat_data[0]
            except (TypeError, IndexError, KeyError):
                scalar = cat_data
            cat_list = [scalar] * n

        if cat_range:
            cat_min, cat_max = min(cat_range), max(cat_range)

        if val_range:
            val_min_p = _parse_datetime_bound(min(val_range))
            val_max_p = _parse_datetime_bound(max(val_range))

        for i, cat_val in enumerate(cat_list):
            # --- Category filter ---
            if cat_range:
                if _is_orderable_value(cat_val) and _is_orderable_value(
                    cat_min
                ):
                    cat_min_p = _parse_datetime_bound(cat_min)
                    cat_max_p = _parse_datetime_bound(cat_max)
                    cat_val_p = _parse_datetime_bound(cat_val)
                    if not (cat_min_p <= cat_val_p <= cat_max_p):
                        continue
                else:
                    pos = _safe_category_get(global_cat_order, cat_val, -1)
                    if pos < 0:
                        continue
                    if not (cat_max > pos - 0.5 and cat_min < pos + 0.5):
                        continue

            # --- Value filter ---
            if val_range:
                val_v = (
                    val_data[i] if hasattr(val_data, "__getitem__") else None
                )
                val_v_p = _parse_datetime_bound(val_v)
                if val_v is None or not (
                    _is_orderable_value(val_v_p)
                    and val_min_p <= val_v_p <= val_max_p
                ):
                    continue

            sample = _build_box_sample_point(trace, trace_idx, i)
            if sample is not None:
                selected.append(sample)

    return selected


def _build_box_sample_point(
    trace: Any, trace_idx: int, point_idx: int
) -> dict[str, Any] | None:
    """Build a row-level selection payload for a single box plot data point."""
    orientation = getattr(trace, "orientation", "v") or "v"
    if orientation == "h":
        val_key, cat_key = "x", "y"
    else:
        val_key, cat_key = "y", "x"

    val_value = _get_indexed_value(getattr(trace, val_key, None), point_idx)
    if val_value is None:
        return None

    cat_source = getattr(trace, cat_key, None)
    if cat_source is None:
        cat_value: Any = getattr(trace, "name", None) or trace_idx
    elif isinstance(cat_source, (str, bytes)):
        cat_value = cat_source
    else:
        try:
            cat_len = (
                len(cat_source) if hasattr(cat_source, "__len__") else None
            )
        except TypeError:
            cat_len = None
        if cat_len == len(getattr(trace, val_key, [])):
            cat_value = _get_indexed_value(cat_source, point_idx)
        else:
            indexed = _get_indexed_value(cat_source, 0)
            cat_value = indexed if indexed is not None else cat_source

    point: dict[str, Any] = {
        val_key: val_value,
        "pointIndex": point_idx,
        "curveNumber": trace_idx,
    }
    if cat_value is not None:
        point[cat_key] = cat_value

    name = getattr(trace, "name", None)
    if name:
        point["name"] = name

    for field in ("customdata", "text", "hovertext"):
        val = _get_indexed_value(getattr(trace, field, None), point_idx)
        if val is not None:
            point[field] = val

    return point


def _extract_violin_points_fallback(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract violin plot data points from a selection range (pure Python).

    Filters by both the category axis (which violin group falls inside the
    selection box) and the value axis (which individual sample values fall
    inside the selection box).  Used when numpy is unavailable.
    """
    x_range = range_data.get("x")
    y_range = range_data.get("y")

    selected: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "violin":
            continue

        orientation = getattr(trace, "orientation", "v") or "v"
        if orientation == "h":
            cat_range = y_range
            val_range = x_range
            cat_data = getattr(trace, "y", None)
            val_data = getattr(trace, "x", None)
        else:
            cat_range = x_range
            val_range = y_range
            cat_data = getattr(trace, "x", None)
            val_data = getattr(trace, "y", None)

        if val_data is None:
            continue

        n = len(val_data)
        if n == 0:
            continue

        if cat_data is None:
            cat_list: list[Any] = [getattr(trace, "name", trace_idx)] * n
        elif hasattr(cat_data, "__len__") and len(cat_data) == n:
            cat_list = list(cat_data)
        else:
            scalar = (
                cat_data[0] if hasattr(cat_data, "__getitem__") else cat_data
            )
            cat_list = [scalar] * n

        if cat_range:
            cat_min, cat_max = min(cat_range), max(cat_range)
            seen_order: dict[Any, int] = {}
            for v in cat_list:
                try:
                    if v not in seen_order:
                        seen_order[v] = len(seen_order)
                except TypeError:
                    pass

        for i, cat_val in enumerate(cat_list):
            if cat_range:
                if _is_orderable_value(cat_val) and _is_orderable_value(
                    cat_min
                ):
                    cat_min_p = _parse_datetime_bound(cat_min)
                    cat_max_p = _parse_datetime_bound(cat_max)
                    cat_val_p = _parse_datetime_bound(cat_val)
                    if not (cat_min_p <= cat_val_p <= cat_max_p):
                        continue
                else:
                    try:
                        pos = seen_order.get(cat_val)
                    except TypeError:
                        continue
                    if pos is None:
                        continue
                    if not (cat_max > pos - 0.5 and cat_min < pos + 0.5):
                        continue

            if val_range:
                val_min_f = float(min(val_range))
                val_max_f = float(max(val_range))
                try:
                    val_f = float(val_data[i])
                    if not (val_min_f <= val_f <= val_max_f):
                        continue
                except (TypeError, ValueError):
                    pass  # non-numeric value; skip value filtering

            sample = _build_violin_sample_point(trace, trace_idx, i)
            if sample is not None:
                selected.append(sample)

    return selected


def _build_violin_sample_point(
    trace: Any, trace_idx: int, point_idx: int
) -> dict[str, Any] | None:
    """Build a row-level selection payload for a single violin plot data point."""
    orientation = getattr(trace, "orientation", "v") or "v"
    if orientation == "h":
        val_key, cat_key = "x", "y"
    else:
        val_key, cat_key = "y", "x"

    val_value = _get_indexed_value(getattr(trace, val_key, None), point_idx)
    if val_value is None:
        return None

    cat_source = getattr(trace, cat_key, None)
    if cat_source is None:
        cat_value: Any = getattr(trace, "name", None) or trace_idx
    elif isinstance(cat_source, (str, bytes)):
        cat_value = cat_source
    else:
        try:
            cat_len = (
                len(cat_source) if hasattr(cat_source, "__len__") else None
            )
        except TypeError:
            cat_len = None
        if cat_len == len(getattr(trace, val_key, [])):
            cat_value = _get_indexed_value(cat_source, point_idx)
        else:
            indexed = _get_indexed_value(cat_source, 0)
            cat_value = indexed if indexed is not None else cat_source

    point: dict[str, Any] = {
        val_key: val_value,
        "pointIndex": point_idx,
        "pointNumber": point_idx,
        "curveNumber": trace_idx,
    }
    if cat_value is not None:
        point[cat_key] = cat_value

    name = getattr(trace, "name", None)
    if name:
        point["name"] = name

    for field in ("customdata", "text", "hovertext"):
        val = _get_indexed_value(getattr(trace, field, None), point_idx)
        if val is not None:
            point[field] = val

    return point


def _append_funnel_points_to_selection(
    figure: go.Figure, selection_data: dict[str, Any]
) -> None:
    """Handle selection data for go.Funnel traces.

    Two cases:
    1. Range selection (dragmode="select"): extract funnel stages whose
       position and value overlap the selection rectangle.
    2. Click selection: points are already populated by the frontend with
       x, y, label, value, and percent metrics — pass them through after
       filtering empty placeholders and re-syncing indices.
    """
    range_value = selection_data.get("range")
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    if isinstance(range_value, dict):
        # Range selection: extract funnel stages within the rectangle.
        funnel_items = _extract_funnel_stages_from_range(
            figure, cast(dict[str, Any], range_value)
        )
        has_real_points = any(all_points)
        if not has_real_points and not funnel_items:
            selection_data["points"] = []
            selection_data["indices"] = []
            return

        seen: set[tuple[int, int]] = set()
        merged_points: list[dict[str, Any]] = []
        merged_indices: list[int] = []

        for point_idx, point in enumerate(all_points):
            if not point:
                continue
            point_id = _get_selection_point_id(point)
            if point_id is not None:
                if point_id in seen:
                    continue
                seen.add(point_id)
            merged_points.append(point)
            if point_idx < len(all_indices) and isinstance(
                all_indices[point_idx], int
            ):
                merged_indices.append(all_indices[point_idx])
            elif point_id is not None:
                merged_indices.append(point_id[1])

        for point in funnel_items:
            point_id = _get_selection_point_id(point)
            if point_id is not None:
                if point_id in seen:
                    continue
                seen.add(point_id)
                merged_indices.append(point_id[1])
            merged_points.append(point)

        selection_data["points"] = merged_points
        selection_data["indices"] = merged_indices
    else:
        # Click selection: clean up empty-dict placeholders from the frontend.
        clean_points = [p for p in all_points if p]
        if not clean_points:
            selection_data["points"] = []
            selection_data["indices"] = []
            return
        # Re-sync indices: prefer what the frontend sent, fall back to pointIndex.
        incoming_index_map = {
            id(p): idx
            for idx, p in zip(all_indices, all_points, strict=False)
            if p and isinstance(idx, int)
        }
        clean_indices: list[int] = []
        for p in clean_points:
            idx = incoming_index_map.get(id(p))
            if isinstance(idx, int):
                clean_indices.append(idx)
            else:
                pi = p.get("pointIndex", p.get("pointNumber"))
                if isinstance(pi, int):
                    clean_indices.append(pi)
        selection_data["points"] = clean_points
        selection_data["indices"] = clean_indices


def _extract_funnel_stages_from_range(
    figure: go.Figure, range_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract funnel stages that fall within a box-selection range.

    go.Funnel is structurally identical to a horizontal/vertical bar chart:
    default orientation has x = numeric values, y = categorical stage labels.
    A stage is selected when its category position is within the y-range AND
    its value bar (from 0 to x) overlaps the x-range.
    """
    if not range_data.get("x") or not range_data.get("y"):
        return []

    x_range = range_data["x"]
    y_range = range_data["y"]
    x_min, x_max = min(x_range), max(x_range)
    y_min, y_max = min(y_range), max(y_range)

    if DependencyManager.numpy.has():
        return _extract_funnel_stages_numpy(figure, x_min, x_max, y_min, y_max)
    return _extract_funnel_stages_fallback(figure, x_min, x_max, y_min, y_max)


def _extract_funnel_stages_numpy(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract funnel stages using numpy for vectorized filtering."""
    import numpy as np

    selected: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "funnel":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        if x_data is None or y_data is None:
            continue

        orientation = getattr(trace, "orientation", "h") or "h"
        if orientation == "h":
            val_data = x_data
            cat_min, cat_max = y_min, y_max
            val_min, val_max = x_min, x_max
        else:
            val_data = y_data
            cat_min, cat_max = x_min, x_max
            val_min, val_max = y_min, y_max

        n = len(val_data) if hasattr(val_data, "__len__") else 0
        if n == 0:
            continue

        try:
            val_arr = np.asarray(val_data, dtype=np.float64)
        except (TypeError, ValueError):
            # Non-numeric entries (e.g. None) in val_data — fall back to the
            # element-wise path so that non-numeric stages are silently skipped.
            numeric_val_min = _to_numeric_bar_value(val_min)
            for i, val in enumerate(val_data):
                if not (cat_max > i - 0.5 and cat_min < i + 0.5):
                    continue
                numeric_val = _to_numeric_bar_value(val)
                if numeric_val is None or (
                    numeric_val_min is not None
                    and numeric_val < numeric_val_min
                ):
                    continue
                selected.append(
                    _build_funnel_stage_point(
                        trace, trace_idx, i, x_data, y_data
                    )
                )
            continue

        # Category axis: each stage occupies position index ± 0.5
        cat_positions = np.arange(n, dtype=np.float64)
        cat_mask = (cat_max > cat_positions - 0.5) & (
            cat_min < cat_positions + 0.5
        )

        # Value axis: funnel bar spans [0, v]; selected if bar overlaps [val_min, val_max].
        # Overlap condition: val_min <= v AND val_max > 0
        if val_max <= 0:
            continue  # selection is entirely in negative space — no overlap possible
        val_mask = val_arr >= val_min

        mask = cat_mask & val_mask
        for i in np.where(mask)[0]:
            selected.append(
                _build_funnel_stage_point(
                    trace, trace_idx, int(i), x_data, y_data
                )
            )

    return selected


def _extract_funnel_stages_fallback(
    figure: go.Figure,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[dict[str, Any]]:
    """Extract funnel stages using pure Python (fallback when numpy unavailable)."""
    selected: list[dict[str, Any]] = []

    for trace_idx, trace in enumerate(figure.data):
        if getattr(trace, "type", None) != "funnel":
            continue

        x_data = getattr(trace, "x", None)
        y_data = getattr(trace, "y", None)
        if x_data is None or y_data is None:
            continue

        orientation = getattr(trace, "orientation", "h") or "h"
        if orientation == "h":
            val_data = x_data
            cat_min, cat_max = y_min, y_max
            val_min, val_max = x_min, x_max
        else:
            val_data = y_data
            cat_min, cat_max = x_min, x_max
            val_min, val_max = y_min, y_max

        # Value axis: funnel bar spans [0, v]; no overlap possible if val_max ≤ 0
        numeric_val_max = _to_numeric_bar_value(val_max)
        if numeric_val_max is None or numeric_val_max <= 0:
            continue

        numeric_val_min = _to_numeric_bar_value(val_min)

        for i, val in enumerate(val_data):
            # Category check: stage i spans (i-0.5, i+0.5)
            cat_in_range = not (cat_max <= i - 0.5 or cat_min >= i + 0.5)
            if not cat_in_range:
                continue

            # Value check: bar [0, val] overlaps selection [val_min, val_max]
            # Overlap: val_min <= val (bar reaches into or touches selection range)
            numeric_val = _to_numeric_bar_value(val)
            if numeric_val is None or (
                numeric_val_min is not None and numeric_val < numeric_val_min
            ):
                continue

            selected.append(
                _build_funnel_stage_point(trace, trace_idx, i, x_data, y_data)
            )

    return selected


def _build_funnel_stage_point(
    trace: Any,
    trace_idx: int,
    point_idx: int,
    x_data: Any,
    y_data: Any,
) -> dict[str, Any]:
    """Build a selection point dict for a single funnel stage."""
    x_val = _get_indexed_value(x_data, point_idx)
    y_val = _get_indexed_value(y_data, point_idx)
    # For horizontal funnels (default): y=category label, x=numeric value.
    # For vertical funnels: x=category label, y=numeric value.
    orientation = getattr(trace, "orientation", "h")
    if orientation == "v":
        label = x_val
        value = y_val
    else:
        label = y_val
        value = x_val
    point: dict[str, Any] = {
        "x": x_val,
        "y": y_val,
        "label": label,
        "value": value,
        "curveNumber": trace_idx,
        "pointIndex": point_idx,
        "pointNumber": point_idx,
    }
    for field in ("customdata", "text", "hovertext"):
        val = _get_indexed_value(getattr(trace, field, None), point_idx)
        if val is not None:
            point[field] = val
    name = getattr(trace, "name", None)
    if name:
        point["name"] = name
    return point


def _append_funnelarea_points_to_selection(
    selection_data: dict[str, Any],
) -> None:
    """Pass through click data for go.FunnelArea traces.

    FunnelArea is a sector-based chart (like sunburst) with no x/y axes, so
    range/lasso selection is not applicable.  The frontend already populates
    selection_data with label, value, and percent metrics on click; this
    function only strips empty-dict placeholders and syncs indices.
    """
    all_points = cast(list[dict[str, Any]], selection_data.get("points", []))
    all_indices = cast(list[Any], selection_data.get("indices", []))

    clean_points = [p for p in all_points if p]
    if not clean_points:
        selection_data["points"] = []
        selection_data["indices"] = []
        return

    incoming_index_map = {
        id(p): idx
        for idx, p in zip(all_indices, all_points, strict=False)
        if p and isinstance(idx, int)
    }
    clean_indices: list[int] = []
    for p in clean_points:
        idx = incoming_index_map.get(id(p))
        if isinstance(idx, int):
            clean_indices.append(idx)
        else:
            pi = p.get("pointNumber")
            if isinstance(pi, int):
                clean_indices.append(pi)
    selection_data["points"] = clean_points
    selection_data["indices"] = clean_indices
