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
        data.cars(),
        x="Horsepower",
        y="Miles_per_Gallon",
        color="Origin"
    )

    plot = mo.ui.plotly(_plot)
    ```

    ```
    # View the plot and selected data
    mo.hstack([plot, plot.value])
    ```

    **Attributes.**

    - `value`: a dict of the plot data
    - `ranges`: the selection of the plot; this may be an interval along
       the name of an axis

    **Initialization Args.**

    - `figure`: A `plotly.graph_objects.Figure`
    - `label`: optional text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    name: Final[str] = "marimo-plotly"

    def __init__(
        self,
        figure: go.Figure,
        *,
        label: str = "",
        on_change: Optional[Callable[[JSONType], None]] = None,
    ) -> None:
        DependencyManager.require_plotly("for `mo.ui.plotly`")

        import plotly.io as pio  # type:ignore

        json_str = pio.to_json(figure)

        super().__init__(
            component_name=plotly.name,
            initial_value={},
            label=label,
            args={
                "figure": json.loads(json_str),
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
