# Copyright 2024 Marimo. All rights reserved.
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

    This function currently only supports scatter plots, treemap charts,
    sunburst charts and heatmaps.

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
                # Skip heatmap traces - they're handled separately below
                if getattr(trace, "type", None) == "heatmap":
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
                range_value = initial_value["range"]
                if isinstance(range_value, dict):
                    heatmap_cells = plotly._extract_heatmap_cells_from_range(
                        figure, cast(dict[str, Any], range_value)
                    )
                    if heatmap_cells:
                        # Append heatmap cells to existing points (e.g., scatter)
                        # instead of replacing them
                        existing_points = initial_value.get("points", [])
                        existing_indices = initial_value.get("indices", [])
                        initial_value["points"] = (
                            existing_points + heatmap_cells
                        )
                        initial_value["indices"] = existing_indices + list(
                            range(
                                len(existing_indices),
                                len(existing_indices) + len(heatmap_cells),
                            )
                        )

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

        # For heatmaps with a range selection, always extract all cells in range
        # (Plotly only sends corner/edge points, not all cells)
        if has_heatmap and value.get("range"):
            range_value = value["range"]
            # Ensure range_value is a dict before processing
            if isinstance(range_value, dict):
                heatmap_cells = self._extract_heatmap_cells_from_range(
                    self._figure, cast(dict[str, Any], range_value)
                )
                if heatmap_cells:
                    self._selection_data["points"] = heatmap_cells
                    # Update indices to match the heatmap cells
                    self._selection_data["indices"] = list(
                        range(len(heatmap_cells))
                    )

        result = self.points
        return result

    @staticmethod
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
            return plotly._extract_heatmap_cells_numpy(
                figure, x_min, x_max, y_min, y_max
            )

        return plotly._extract_heatmap_cells_fallback(
            figure, x_min, x_max, y_min, y_max
        )

    @staticmethod
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

    @staticmethod
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
