# Copyright 2024 Marimo. All rights reserved.
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
    import altair  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
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
    df: pd.DataFrame, selection: ChartSelection
) -> pd.DataFrame:
    import numpy as np

    for channel, fields in selection.items():
        # Don't filter on pan_zoom
        if channel.startswith("pan_zoom"):
            continue
        # This is a case when altair does not pass back the fields to filter on
        # and instead passes an individual selected point.
        if len(fields) == 2 and "vlPoint" in fields and "_vgsid_" in fields:
            # Vega is 1-indexed, so subtract 1
            indexes = [int(i) - 1 for i in fields["_vgsid_"]]
            df = df.iloc[indexes]
            continue

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
                left_value = _coerce_value(dtype, resolved_values[0])
                right_value = _coerce_value(dtype, resolved_values[1])
                df = df[(df[field] >= left_value) & (df[field] <= right_value)]
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


def _coerce_value(dtype: Any, value: Any) -> Any:
    # If dtype is datetime[ns], then we need to convert the value
    # from milliseconds (which is what vega returns for dates)
    if dtype == "datetime64[ns]":
        import pandas as pd

        return pd.to_datetime(value, unit="ms")

    if dtype == "object":
        return str(value)

    return value


def _parse_spec(spec: altair.TopLevelMixin) -> VegaSpec:
    import altair

    # vegafusion requires creating a vega spec,
    # instead of using a vega-lite spec
    if altair.data_transformers.active == "vegafusion":
        return spec.to_dict(format="vega")  # type: ignore
    with altair.data_transformers.enable("marimo"):
        return spec.to_dict()  # type: ignore


def _has_transforms(spec: VegaSpec) -> bool:
    """Return True if the spec has transforms."""
    return "transform" in spec and len(spec["transform"]) > 0


@mddoc
class altair_chart(UIElement[ChartSelection, "pd.DataFrame"]):
    """Make reactive charts with Altair

    Use `mo.ui.altair_chart` to make Altair charts reactive: select chart data
    with your cursor on the frontend, get them as a Pandas dataframe in Python!

    For Polars DataFrames, you can convert to a Pandas DataFrame.
    However the returned DataFrame will still be a Pandas DataFrame,
    so you will need to convert back to a Polars DataFrame if you want.

    **Example.**

    ```python
    import altair as alt
    import marimo as mo
    from vega_datasets import data

    chart = (
        alt.Chart(data.cars())
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
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
        enable selection, `True` to enable selection for all fields, or
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

        register_transformers()

        self._chart = chart

        if not isinstance(chart, (alt.TopLevelMixin)):
            raise ValueError(
                "Invalid type for chart: "
                f"{type(chart)}; expected altair.Chart"
            )

        # Make full-width if no width is specified
        if (
            isinstance(chart, (alt.Chart, alt.LayerChart))
            and chart.width is alt.Undefined
        ):
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

        # Types say this is not possible,
        # but a user still may pass none
        if chart_selection is None:  # type: ignore
            chart_selection = False
        if legend_selection is None:  # type: ignore
            legend_selection = False

        # Selection for binned charts is not yet implemented
        has_chart_selection = chart_selection is not False
        has_legend_selection = legend_selection is not False
        if _has_binning(vega_spec) and (
            has_chart_selection or has_legend_selection
        ):
            sys.stderr.write(
                "Binning + selection is not yet supported in "
                "marimo.ui.chart.\n"
                "If you'd like this feature, please file an issue: "
                "https://github.com/marimo-team/marimo/issues\n"
            )
            chart_selection = False
            legend_selection = False

        self.dataframe = self._get_dataframe_from_chart(chart)

        self._spec = vega_spec

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

    @staticmethod
    def _get_dataframe_from_chart(
        chart: altair.Chart,
    ) -> Union[pd.DataFrame, altair.UndefinedType]:
        import pandas as pd

        if isinstance(chart.data, str) and chart.data.endswith(".csv"):
            return pd.read_csv(chart.data)
        if isinstance(chart.data, str) and chart.data.endswith(".json"):
            return pd.read_json(chart.data)

        return chart.data

    def _convert_value(self, value: ChartSelection) -> Any:
        from altair import UndefinedType

        self._chart_selection = value
        flat, _ = flatten.flatten(value)
        if not value or not flat:
            import pandas as pd

            return pd.DataFrame()

        # When using layered charts, you can no longer access the
        # chart data directly
        # Instead, we should push user to call .apply_selection(df)
        if isinstance(self.dataframe, UndefinedType):
            return self.dataframe

        # If we have transforms, we need to filter the dataframe
        # with those transforms, before applying the selection
        if _has_transforms(self._spec):
            try:
                df: pd.DataFrame = self._chart.transformed_data()
                return _filter_dataframe(df, value)
            except ImportError as e:
                sys.stderr.write(
                    "Failed to filter dataframe that includes a transform. "
                    + "This could be due to a missing dependency.\n\n"
                    + e.msg
                )
                # Fall back to the untransformed dataframe
                return _filter_dataframe(self.dataframe, value)

        return _filter_dataframe(self.dataframe, value)

    def apply_selection(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the selection to a DataFrame.

        This method is useful when you have a layered chart and you want to
        apply the selection to a DataFrame.

        **Example.**

        ```python
        import altair as alt
        import marimo as mo
        from vega_datasets import data

        cars = data.cars()

        _chart = (
            alt.Chart(cars)
            .mark_point()
            .encode(
                x="Horsepower",
                y="Miles_per_Gallon",
                color="Origin",
            )
        )

        chart = mo.ui.altair_chart(_chart)
        chart

        # In another cell
        selected_df = chart.apply_selection(cars)
        ```

        **Args.**

        - `df`: a Pandas DataFrame to apply the selection to

        **Returns.**

        - a Pandas DataFrame of the plot data filtered by the selections
        """
        return _filter_dataframe(df, self.selections)

    # Proxy all of altair's attributes
    def __getattr__(self, name: str) -> Any:
        return getattr(self._chart, name)

    def __add__(self, other: Any) -> Any:
        if isinstance(other, altair_chart):
            other = other._chart
        return altair_chart(self._chart + other)

    def __or__(self, value: Any) -> Any:
        if isinstance(value, altair_chart):
            value = value._chart
        return altair_chart(self._chart | value)

    def __radd__(self, other: Any) -> Any:
        if isinstance(other, altair_chart):
            other = other._chart
        return altair_chart(other + self._chart)

    def __ror__(self, value: Any) -> Any:
        if isinstance(value, altair_chart):
            value = value._chart
        return altair_chart(value | self._chart)

    def __and__(self, value: Any) -> Any:
        if isinstance(value, altair_chart):
            value = value._chart
        return altair_chart(self._chart & value)

    @property
    def value(self) -> pd.DataFrame:
        from altair import UndefinedType

        value = super().value
        if isinstance(value, UndefinedType):
            sys.stderr.write(
                "The underlying chart data is not available in layered"
                " or stacked charts. "
                "Use `.apply_selection(df)` to filter a DataFrame"
                " based on the selection.",
            )
        return value

    @value.setter
    def value(self, value: pd.DataFrame) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")
