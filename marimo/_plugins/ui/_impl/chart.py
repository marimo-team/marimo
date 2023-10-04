# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, Dict, Final, List, Literal, Optional, Union

from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import altair

# Selection is a dictionary of the form:
# {
#   "signal_channel": {
#     "field": ["value1", "value2", ...]
#   }
# }
ChartSelection = Dict[str, Dict[str, Union[List[int], List[float], List[str]]]]


@mddoc
class chart(UIElement[ChartSelection, list]):
    """Render a Vega-Lite spec or Altair chart

    Use `mo.ui.chart` to render an interactive chart.

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

    mo.ui.chart(chart)
    ```

    **Attributes.**

    - `value`: the data if the chart has any selections
    - `selections`: the selection of the chart
        this could be an interval along the name of an axis
        or a selection of points
    - `dataframe`: the data used to render the chart as a pandas DataFrame

    **Initialization Args.**

    - `spec`: the Vega-Lite chart specification
    - `label`: optional text label for the element
    - `selection_chart`: optional selection type,
        either `point` or `interval` or boolean.
        defaults to `True` which will automatically detect
        the best selection type.
    - `selection_fields`: optional list of fields to select,
        either list of strings or boolean.
        defaults to `True` which will automatically selects all fields used in the chart
    - `on_change`: optional callback to run when this element's value changes
    """

    name: Final[str] = "marimo-vega"

    def __init__(
        self,
        spec: Union[str, altair.Chart, dict],
        selection_chart: Union[
            Literal["point"], Literal["interval"], bool
        ] = True,
        selection_fields: Union[List[str], bool] = True,
        *,
        label: str = "",
        on_change: Optional[Callable[[list], None]] = None,
    ) -> None:
        vega_spec = _parse_spec(spec)
        self.dataframe = _to_dataframe(vega_spec)

        if label:
            vega_spec["title"] = label

        # Automatically add full width
        if not "width" in vega_spec:
            vega_spec["width"] = "container"
        if "vconcat" in vega_spec:
            for chart in vega_spec["vconcat"]:
                if not "width" in chart:
                    chart["width"] = "container"

        super().__init__(
            component_name="marimo-vega",
            initial_value={},
            label=label,
            args={
                "spec": vega_spec,
                "selection-chart": selection_chart,
                "selection-fields": selection_fields,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: ChartSelection) -> Any:
        if value is None:
            return []
        return _filter_dataframe(self.dataframe, value)

    def selections(self) -> ChartSelection:
        return self.value



def _to_dataframe(vega_spec: dict) -> list:
    # Try to import pandas
    try:
        import pandas as pd
    except ImportError:
        LOGGER.error("Pandas is required to render Vega-Lite charts")
        raise ImportError("Pandas is required to render Vega-Lite charts")

    data = vega_spec.get("data", {})
    if "url" in data:
        # If the data is defined as a URL, use pandas to read the data from the URL
        if data["url"].endswith(".csv"):
            df = pd.read_csv(data["url"])
        elif data["url"].endswith(".json"):
            df = pd.read_json(data["url"])
        else:
            raise ValueError(f'Unsupported data format: {data["url"]}')
    elif "values" in data:
        # If the data is defined as an inline list, convert the list to a DataFrame
        df = pd.DataFrame(data["values"])
    elif "name" in data:
        # If the data is defined as a named data source, try to find the data source
        # in the Vega-Lite spec
        name = data["name"]
        datasets = vega_spec.get("datasets", {})
        if name in datasets:
            df = pd.DataFrame(datasets[name])
        else:
            raise ValueError(f"Could not find data source {name}")
    else:
        raise ValueError("Data source not supported")
    return df


def _filter_dataframe(df: list, selection: ChartSelection) -> list:
    # Try to import pandas
    try:
        import pandas as pd
    except ImportError:
        LOGGER.error("Pandas is required to render Vega-Lite charts")
        raise ImportError("Pandas is required to render Vega-Lite charts")

    for _channel, fields in selection.items():
        # if vlPoint is in the selection, then the selection is a point selection
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

def _parse_spec(spec: Union[str, altair.Chart, dict]) -> dict:
    if spec is None or spec == "":
        return {}

    # Parse Altair chart, str, or dict
    try:
        try:
            import altair
            if isinstance(spec, altair.Chart):
                return json.loads(spec.to_json())
        except:
            pass

        if isinstance(spec, dict):
            return spec
        elif isinstance(spec, str):
            return json.loads(spec)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid Vega-Lite spec: {spec}")

    raise ValueError("Invalid Vega-Lite spec")
