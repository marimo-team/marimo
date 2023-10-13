# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Final,
    List,
    Literal,
    Optional,
    Union,
)

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.charts.altair_transformer import (
    register_transformers,
)
from marimo._utils import flatten

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import altair  # type:ignore[import]
    import pandas as pd

# Selection is a dictionary of the form:
# {
#   "signal_channel": {
#     "field": ["value1", "value2", ...]
#   }
# }
ChartSelection = Dict[str, Dict[str, Union[List[int], List[float], List[str]]]]
VegaSpec = Dict[str, Any]


def _has_binning(spec: VegaSpec) -> bool:
    """Return True if the spec has binning."""
    if "encoding" not in spec:
        return False
    for encoding in spec["encoding"].values():
        if "bin" in encoding:
            return True
    return False


def _filter_dataframe(
    df_prev: pd.DataFrame, selection: ChartSelection
) -> pd.DataFrame:
    import numpy as np

    # Make a copy of the DataFrame
    df = df_prev.copy()

    for _channel, fields in selection.items():
        # If vlPoint is in the selection,
        # then the selection is a point selection
        # otherwise, it is an interval selection
        is_point_selection = "vlPoint" in fields
        for field, values in fields.items():
            # Skip vlPoint and _vgsid_ field
            if field == "vlPoint" or field == "_vgsid_":
                continue

            # values may come back as strings if using the CSV transformer;
            # convert back to original datatype
            dtype = df[field].dtype
            try:
                resolved_values = [dtype.type(v) for v in values]
            except Exception:
                resolved_values = values  # type: ignore[assignment]
            del values
            if is_point_selection:
                df = df[df[field].isin(resolved_values)]
            elif len(resolved_values) == 1:
                df = df[df[field] == resolved_values[0]]
            # Range selection
            elif len(resolved_values) == 2 and isinstance(
                resolved_values[0], (int, float, np.number)
            ):
                df = df[
                    (df[field] >= resolved_values[0])
                    & (df[field] <= resolved_values[1])
                ]
            # Multi-selection via range
            # This can happen when you use an interval selection
            # on categorical data
            elif len(resolved_values) > 1:
                df = df[df[field].isin(resolved_values)]
            else:
                raise ValueError(
                    f"Invalid selection: {field}={resolved_values}"
                ) from None
    return df


def _parse_spec(spec: altair.TopLevelMixin) -> VegaSpec:
    import altair

    # vegafusion requires creating a vega spec,
    # instead of using a vega-lite spec
    if altair.data_transformers.active == "vegafusion":
        return spec.to_dict(format="vega")  # type: ignore
    return spec.to_dict()  # type: ignore


@mddoc
class altair_chart(UIElement[ChartSelection, "pd.DataFrame"]):
    """Make reactive charts with Altair

    Use `mo.ui.altair_chart` to make Altair charts reactive: select chart data
    with your cursor on the frontend, get them as a Pandas dataframe in Python!

    **Example.**

    ```python
    import altair as alt
    import marimo as mo
    from vega_datasets import data

    chart = alt.Chart(data.cars()).mark_point().encode(
        x='Horsepower',
        y='Miles_per_Gallon',
        color='Origin',
    )

    chart = mo.ui.altair_chart(chart)
    ```

    ```
    # View the chart and selected data as a dataframe
    mo.hstack([chart, chart.value])
    ```

    **Attributes.**

    - `value`: a Pandas dataframe of the plot data filtered by the selections
    - `dataframe`: a Pandas dataframe of the unfiltered chart data
    - `selections`: the selection of the chart; this may be an interval along
       the name of an axis or a selection of points

    **Initialization Args.**

    - `chart`: An `altair.Chart`
    - `chart_selection`: optional selection type,
        `"point"`, `"interval"`, or a bool; defaults to `True` which will
        automatically detect the best selection type
    - `legend_selection`: optional list of legend fields (columns) for which to
        enable selecton, `True` to enable selection for all fields, or
        `False` to disable selection entirely
    - `label`: optional text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    name: Final[str] = "marimo-vega"

    def __init__(
        self,
        chart: altair.Chart,
        chart_selection: Literal["point"] | Literal["interval"] | bool = True,
        legend_selection: list[str] | bool = True,
        *,
        label: str = "",
        on_change: Optional[Callable[[pd.DataFrame], None]] = None,
    ) -> None:
        DependencyManager.require_altair(why="to use `mo.ui.altair_chart`")

        import altair as alt

        # TODO: is this the right place to register the transformers?
        register_transformers()

        if not isinstance(chart, (alt.TopLevelMixin)):
            raise ValueError(
                "Invalid type for chart: "
                f"{type(chart)}; expected altair.Chart"
            )

        if isinstance(chart, (alt.Chart, alt.LayerChart)):
            chart = chart.properties(width="container")

        vega_spec = _parse_spec(chart)

        if label:
            vega_spec["title"] = label

        # Fix the sizing for vconcat charts
        if "vconcat" in vega_spec:
            for subchart in vega_spec["vconcat"]:
                if "width" not in subchart:
                    subchart["width"] = "container"
            # without autosize, vconcat will overflow
            if "autosize" not in vega_spec:
                vega_spec["autosize"] = "fit-x"

        # Selection for binned charts is not yet implemented
        if _has_binning(vega_spec):
            sys.stderr.write(
                "Binning + selection is not yet supported in "
                "marimo.ui.chart.\n"
                "If you'd like this feature, please file an issue: "
                "https://github.com/marimo-team/marimo/issues\n"
            )
            chart_selection = False
            legend_selection = False

        self.dataframe = chart.data

        super().__init__(
            component_name="marimo-vega",
            initial_value={},
            label=label,
            args={
                "spec": vega_spec,
                "chart-selection": chart_selection,
                "field-selection": legend_selection,
            },
            on_change=on_change,
        )

    @property
    def selections(self) -> ChartSelection:
        return self._chart_selection

    def _convert_value(self, value: ChartSelection) -> Any:
        self._chart_selection = value
        flat, _ = flatten.flatten(value)
        if not value or not flat:
            import pandas as pd

            return pd.DataFrame()
        return _filter_dataframe(self.dataframe, value)
