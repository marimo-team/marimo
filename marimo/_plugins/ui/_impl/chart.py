# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json
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
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import altair
    import pandas as pd

# Selection is a dictionary of the form:
# {
#   "signal_channel": {
#     "field": ["value1", "value2", ...]
#   }
# }
ChartSelection = Dict[str, Dict[str, Union[List[int], List[float], List[str]]]]
VegaSpec = Dict[str, Any]


@mddoc
class chart(UIElement[ChartSelection, "pd.DataFrame"]):
    """Make reactive charts with Altair

    Use `mo.ui.chart` to make Altair charts reactive: select chart data points
    with your cursor on the frontend, get it as a Pandas dataframe in Python!

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

    chart = mo.ui.chart(chart)
    ```

    ```
    # View the chart and selected data as a dataframe
    mo.hstack([chart, chart.value])
    ```

    **Attributes.**

    - `value`: the data if the chart has any selections
    - `selections`: the selection of the chart; this may be an interval along
        the name of an axis or a selection of points
    - `dataframe`: a Pandas dataframe of the unfiltered chart data

    **Initialization Args.**

    - `chart`: An `altair.Chart` or a Vega-lite spec
    - `chart_selection`: optional selection type,
        `"point"`, `"interval"`, or a bool; defaults to `True` which will
        automatically detect the best selection type
    - `field_selection`: optional list of fields (columns) for which to
        enable selecton, `True` to enable selection for all legend items, or
        `False` to disable selection entirely
    - `label`: optional text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    name: Final[str] = "marimo-vega"

    def __init__(
        self,
        figure: Union[str, altair.Chart, VegaSpec],
        chart_selection: Union[
            Literal["point"], Literal["interval"], bool
        ] = True,
        field_selection: Union[List[str], bool] = True,
        *,
        label: str = "",
        on_change: Optional[Callable[[pd.DataFrame], None]] = None,
    ) -> None:
        vega_spec = _parse_spec(figure)
        self.dataframe = _to_dataframe(vega_spec)

        if label:
            vega_spec["title"] = label

        # Automatically add full width
        if "width" not in vega_spec:
            vega_spec["width"] = "container"
        if "vconcat" in vega_spec:
            for chart in vega_spec["vconcat"]:
                if "width" not in chart:
                    chart["width"] = "container"
            # without autosize, vconcat will overflow
            if "autosize" not in vega_spec:
                vega_spec["autosize"] = "fit-x"

        super().__init__(
            component_name="marimo-vega",
            initial_value={},
            label=label,
            args={
                "spec": vega_spec,
                "chart-selection": chart_selection,
                "field-selection": field_selection,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: ChartSelection) -> Any:
        self._chart_selection = value
        if not value:
            import pandas as pd

            return pd.DataFrame()
        return _filter_dataframe(self.dataframe, value)

    def selections(self) -> ChartSelection:
        return self._chart_selection


def _to_dataframe(vega_spec: VegaSpec) -> pd.DataFrame:
    # Try to import pandas
    try:
        import pandas as pd
    except ImportError:
        LOGGER.error("Pandas is required to render Vega-Lite charts")
        raise ImportError(
            "Pandas is required to render Vega-Lite charts"
        ) from None

    data = vega_spec.get("data", {})
    if "url" in data:
        # If the data is defined as a URL,
        # use pandas to read the data from the URL
        if data["url"].endswith(".csv"):
            df = pd.read_csv(data["url"])
        elif data["url"].endswith(".json"):
            df = pd.read_json(data["url"])
        else:
            raise ValueError(
                f'Unsupported data format: {data["url"]}'
            ) from None
    elif "values" in data:
        # If the data is defined as an inline list,
        # convert the list to a DataFrame
        df = pd.DataFrame(data["values"])
    elif "name" in data:
        # If the data is defined as a named data source,
        # try to find the data source in the Vega-Lite spec
        name = data["name"]
        datasets = vega_spec.get("datasets", {})
        if name in datasets:
            df = pd.DataFrame(datasets[name])
        else:
            raise ValueError(f"Could not find data source {name}") from None
    else:
        raise ValueError("Data source not supported") from None
    return df


def _filter_dataframe(
    df: pd.DataFrame, selection: ChartSelection
) -> pd.DataFrame:
    for _channel, fields in selection.items():
        # If vlPoint is in the selection,
        # then the selection is a point selection
        # otherwise, it is an interval selection
        is_point_selection = "vlPoint" in fields
        for field, values in fields.items():
            # Skip vlPoint field
            if field == "vlPoint":
                continue
            if is_point_selection:
                df = df[df[field].isin(values)]
            else:
                df = df[(df[field] >= values[0]) & (df[field] <= values[1])]
    return df


def _parse_spec(spec: Union[str, altair.Chart, VegaSpec]) -> VegaSpec:
    if spec is None or spec == "":
        return {}

    # Parse Altair chart, str, or dict
    try:
        try:
            import altair

            if isinstance(spec, altair.Chart):
                return json.loads(spec.to_json())  # type: ignore
        except ImportError:
            pass

        if isinstance(spec, dict):
            return spec
        elif isinstance(spec, str):
            return json.loads(spec)  # type: ignore
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid Vega-Lite spec: {spec}") from err

    raise ValueError("Invalid Vega-Lite spec") from None
