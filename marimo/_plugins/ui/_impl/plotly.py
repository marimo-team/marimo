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

    This function currently supports scatter plots, treemaps charts,
    sunbursts charts, and parallel coordinates charts.

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

        # Store the figure data for parallel coordinates processing
        self._figure_data = json.loads(json_str)
        
        # For parallel coordinates, initialize with all data
        initial_value = {}
        if self._is_parallel_coordinates_data(self._figure_data):
            initial_value = {"range": {}}  # Empty constraints = all data
        
        super().__init__(
            component_name=plotly.name,
            initial_value=initial_value,
            label=label,
            args={
                "figure": self._figure_data,
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
        
        # For parallel coordinates plots, we need to handle range-based filtering
        if self._is_parallel_coordinates():
            constraints = value.get("range", {}) if value else {}
            return self._filter_parallel_coordinates_data(constraints)
        
        # Default to returning the points
        return self.points

    def _is_parallel_coordinates(self) -> bool:
        """Check if this is a parallel coordinates plot."""
        if not hasattr(self, '_figure_data'):
            return False
        return self._is_parallel_coordinates_data(self._figure_data)
    
    @staticmethod
    def _is_parallel_coordinates_data(figure_data: dict) -> bool:
        """Check if figure data contains parallel coordinates traces."""
        # Check if any trace is a parcoords type
        for trace in figure_data.get('data', []):
            if trace.get('type') == 'parcoords':
                return True
        return False

    def _filter_parallel_coordinates_data(self, constraints: dict) -> list[dict[str, Any]]:
        """Filter parallel coordinates data based on constraints."""
        if not hasattr(self, '_figure_data'):
            return []
        
        # Find the parcoords trace
        parcoords_trace = None
        for trace in self._figure_data.get('data', []):
            if trace.get('type') == 'parcoords':
                parcoords_trace = trace
                break
        
        if not parcoords_trace or 'dimensions' not in parcoords_trace:
            return []
        
        dimensions = parcoords_trace['dimensions']
        if not dimensions:
            return []
        
        # Decode dimension values from binary data
        decoded_dimensions = []
        for dimension in dimensions:
            label = dimension.get('label', '')
            values_data = dimension.get('values', [])
            
            # Handle binary encoded values
            if isinstance(values_data, dict) and 'bdata' in values_data:
                try:
                    import base64
                    import struct
                    
                    # Decode base64 data
                    binary_data = base64.b64decode(values_data['bdata'])
                    
                    # Unpack binary data as float64 values
                    dtype = values_data.get('dtype', 'f8')
                    if dtype == 'f8':  # float64
                        num_values = len(binary_data) // 8
                        values = list(struct.unpack(f'{num_values}d', binary_data))
                    else:
                        # Fallback for other dtypes
                        values = []
                except Exception:
                    values = []
            elif isinstance(values_data, list):
                values = values_data
            else:
                values = []
                
            decoded_dimensions.append({
                'label': label,
                'values': values
            })
        
        # Extract all data points
        all_points = []
        if decoded_dimensions and decoded_dimensions[0]['values']:
            num_points = len(decoded_dimensions[0]['values'])
            
            for i in range(num_points):
                point = {}
                for dim_idx, dimension in enumerate(decoded_dimensions):
                    label = dimension['label'] or f'dimension_{dim_idx}'
                    values = dimension['values']
                    if i < len(values):
                        point[label] = values[i]
                if point:  # Only add if we have data
                    all_points.append(point)
        
        # If no constraints, return all points
        if not constraints:
            return all_points
        
        # Apply constraints to filter points
        filtered_points = []
        for point in all_points:
            include_point = True
            for constraint_key, constraint_ranges in constraints.items():
                # constraint_key is like "dimension_0"
                try:
                    dim_idx = int(constraint_key.split('_')[1])
                    if dim_idx < len(decoded_dimensions):
                        dimension = decoded_dimensions[dim_idx]
                        label = dimension['label'] or f'dimension_{dim_idx}'
                        if label in point:
                            value = point[label]
                            # Check if value falls within any of the constraint ranges
                            within_range = False
                            for min_val, max_val in constraint_ranges:
                                if min_val <= value <= max_val:
                                    within_range = True
                                    break
                            if not within_range:
                                include_point = False
                                break
                except (ValueError, IndexError):
                    # Skip invalid constraint keys
                    continue
            
            if include_point:
                filtered_points.append(point)
        
        return filtered_points
