# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Final,
    List,
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
PlotlySelection = Dict[str, JSONType]


@mddoc
class plotly(UIElement[PlotlySelection, List[Dict[str, Any]]]):
    """Make reactive plots with Plotly.

    Use `mo.ui.plotly` to make plotly plots reactive: select data
    with your cursor on the frontend, get them as a list of dicts in Python!

    **Example.**

    ```python
    import plotly.express as px
    import marimo as mo
    from vega_datasets import data

    _plot = px.scatter(
        data.cars(), x="Horsepower", y="Miles_per_Gallon", color="Origin"
    )

    plot = mo.ui.plotly(_plot)
    ```

    ```
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

    **Attributes.**

    - `value`: a dict of the plot data
    - `ranges`: the selection of the plot; this may be an interval along
       the name of an axis

    **Initialization Args.**

    - `figure`: A `plotly.graph_objects.Figure`
    - `config`: optional configuration for the plot
        This is a dictionary that is passed directly to the plotly.
        See the plotly documentation for more information:
        https://plotly.com/javascript/configuration-options/
        This takes precedence over the default configuration of the renderer.
    - `renderer_name`: optional renderer to use for the plot.
        If this is not provided, the default renderer (pio.renderers.default)
        is used.
    - `label`: optional text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    name: Final[str] = "marimo-plotly"

    def __init__(
        self,
        figure: go.Figure,
        config: Optional[Dict[str, Any]] = None,
        renderer_name: Optional[str] = None,
        *,
        label: str = "",
        on_change: Optional[Callable[[JSONType], None]] = None,
    ) -> None:
        DependencyManager.plotly.require("for `mo.ui.plotly`")

        import plotly.io as pio  # type:ignore

        json_str = pio.to_json(figure)

        resolved_config: Dict[str, Any] = {}
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

        super().__init__(
            component_name=plotly.name,
            initial_value={},
            label=label,
            args={
                "figure": json.loads(json_str),
                "config": resolved_config,
            },
            on_change=on_change,
        )

    @property
    def ranges(self) -> Dict[str, List[float]]:
        if not self._selection_data:
            return {}
        if "range" not in self._selection_data:
            return {}
        return self._selection_data["range"]  # type:ignore

    @property
    def points(self) -> List[Dict[str, Any]]:
        if not self._selection_data:
            return []
        if "points" not in self._selection_data:
            return []
        return self._selection_data["points"]  # type:ignore

    @property
    def indices(self) -> List[int]:
        if not self._selection_data:
            return []
        if "indices" not in self._selection_data:
            return []
        return self._selection_data["indices"]  # type:ignore

    def _convert_value(self, value: PlotlySelection) -> Any:
        # Store the selection data
        self._selection_data = value
        # Default to returning the points
        return self.points
