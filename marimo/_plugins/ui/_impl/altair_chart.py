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
    import polars as pl

# Selection is a dictionary of the form:
# {
#   "signal_channel": {
#     "field": ["value1", "value2", ...]
#   }
# }
ChartSelection = Dict[str, Dict[str, Union[List[int], List[float], List[str]]]]
VegaSpec = Dict[str, Any]

ChartDataType = Union["pd.DataFrame", "pl.DataFrame"]


def _has_binning(spec: VegaSpec) -> bool:
    """Return True if the spec has binning."""
    if "encoding" not in spec:
        return False
    for encoding in spec["encoding"].values():
        if "bin" in encoding:
            return True
    return False


def _has_geoshape(spec: altair.TopLevelMixin) -> bool:
    """Return True if the spec has geoshape."""
    try:
        if not hasattr(spec, "mark"):
            return False
        mark = spec.mark  # type: ignore
        return mark == "geoshape" or mark.type == "geoshape"  # type: ignore
    except Exception:
        return False


def _filter_dataframe(
    df: ChartDataType, selection: Dict[str, Any]
) -> ChartDataType:
    if not isinstance(selection, dict):
        raise TypeError("Input 'selection' must be a dictionary")

    if DependencyManager.pandas.imported():
        import pandas as pd

        if isinstance(df, pd.DataFrame):
            return _filter_pandas_dataframe(df, selection)

    if DependencyManager.polars.imported():
        import polars as pl

        if isinstance(df, pl.DataFrame):
            return _filter_polars_dataframe(df, selection)

    raise TypeError("Input 'df' must be a pandas or polars DataFrame")


def _filter_pandas_dataframe(
    df: pd.DataFrame, selection: Dict[str, Any]
) -> pd.DataFrame:
    for channel, fields in selection.items():
        if not isinstance(channel, str) or not isinstance(fields, dict):
            raise ValueError(
                f"Invalid selection format for channel: {channel}"
            )

        # Don't filter on pan_zoom
        if channel.startswith("pan_zoom"):
            continue

        # This is a case when altair does not pass back the fields to filter on
        # and instead passes an individual selected point.
        if len(fields) == 2 and "vlPoint" in fields and "_vgsid_" in fields:
            # Vega is 1-indexed, so subtract 1
            try:
                indexes = [int(i) - 1 for i in fields["_vgsid_"]]
                df = df.iloc[indexes]
            except (ValueError, IndexError) as e:
                raise ValueError(
                    f"Invalid index in selection: {fields['_vgsid_']}"
                ) from e
            continue

        # If vlPoint is in the selection,
        # then the selection is a point selection
        # otherwise, it is an interval selection
        is_point_selection = "vlPoint" in fields
        for field, values in fields.items():
            # values may come back as strings if using the CSV transformer;
            # convert back to original datatype
            if field in ("vlPoint", "_vgsid_"):
                continue

            if field not in df.columns:
                raise ValueError(f"Field '{field}' not found in DataFrame")

            dtype = df[field].dtype
            resolved_values = _resolve_values_pandas(values, dtype)

            if is_point_selection:
                df = df[df[field].isin(resolved_values)]
            elif len(resolved_values) == 1:
                df = df[df[field] == resolved_values[0]]
            # Range selection
            elif len(resolved_values) == 2 and _is_numeric(values[0]):
                left_value, right_value = resolved_values
                df = df[(df[field] >= left_value) & (df[field] <= right_value)]
            # Multi-selection via range
            # This can happen when you use an interval selection
            # on categorical data
            elif len(resolved_values) > 1:
                df = df[df[field].isin(resolved_values)]
            else:
                raise ValueError(
                    f"Invalid selection: {field}={resolved_values}"
                )

    return df


def _filter_polars_dataframe(
    df: pl.DataFrame, selection: Dict[str, Any]
) -> pl.DataFrame:
    import polars as pl

    for channel, fields in selection.items():
        if not isinstance(channel, str) or not isinstance(fields, dict):
            raise ValueError(
                f"Invalid selection format for channel: {channel}"
            )

        # Don't filter on pan_zoom
        if channel.startswith("pan_zoom"):
            continue

        # This is a case when altair does not pass back the fields to filter on
        # and instead passes an individual selected point.
        if len(fields) == 2 and "vlPoint" in fields and "_vgsid_" in fields:
            # Vega is 1-indexed, so subtract 1
            try:
                indexes = [int(i) - 1 for i in fields["_vgsid_"]]
                df = df.filter(pl.arange(0, df.height).is_in(indexes))
            except (ValueError, IndexError) as e:
                raise ValueError(
                    f"Invalid index in selection: {fields['_vgsid_']}"
                ) from e
            continue

        # If vlPoint is in the selection,
        # then the selection is a point selection
        # otherwise, it is an interval selection
        is_point_selection = "vlPoint" in fields
        for field, values in fields.items():
            # values may come back as strings if using the CSV transformer;
            # convert back to original datatype
            if field in ("vlPoint", "_vgsid_"):
                continue

            if field not in df.columns:
                raise ValueError(f"Field '{field}' not found in DataFrame")

            dtype = df[field].dtype
            resolved_values = _resolve_values_polars(values, dtype)

            if is_point_selection:
                df = df.filter(pl.col(field).is_in(resolved_values))
            elif len(resolved_values) == 1:
                df = df.filter(pl.col(field) == resolved_values[0])
            # Range selection
            elif len(resolved_values) == 2 and _is_numeric(values[0]):
                left_value, right_value = resolved_values
                df = df.filter(
                    (pl.col(field) >= left_value)
                    & (pl.col(field) <= right_value)
                )
            # Multi-selection via range
            # This can happen when you use an interval selection
            # on categorical data
            elif len(resolved_values) > 1:
                df = df.filter(pl.col(field).is_in(resolved_values))
            else:
                raise ValueError(
                    f"Invalid selection: {field}={resolved_values}"
                )

    return df


def _resolve_values_polars(values: Any, dtype: Any) -> List[Any]:
    import polars as pl

    def _coerce_value(value: Any, dtype: Any) -> Any:
        if pl.datatypes.Date == dtype or pl.datatypes.Datetime == dtype:
            # Value is milliseconds since epoch
            import datetime

            return datetime.datetime.fromtimestamp(value / 1000).date()
        return value

    if isinstance(values, list):
        return [_coerce_value(v, dtype) for v in values]
    return [_coerce_value(values, dtype)]


def _resolve_values_pandas(values: Any, dtype: Any) -> List[Any]:
    import numpy as np
    import pandas as pd

    def _coerce_value(value: Any, dtype: Any) -> Any:
        if dtype == "datetime64[ns]":
            return pd.to_datetime(value, unit="ms")
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return pd.to_datetime(value, unit="ms")
        if dtype == "object":
            return str(value)

        return np.array([value]).astype(dtype)[0]

    if isinstance(values, list):
        return [_coerce_value(v, dtype) for v in values]
    return [_coerce_value(values, dtype)]


def _is_numeric(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True

    if DependencyManager.numpy.has():
        import numpy as np

        if isinstance(value, np.number):
            return True

    return False


def _parse_spec(spec: altair.TopLevelMixin) -> VegaSpec:
    import altair

    # vegafusion requires creating a vega spec,
    # instead of using a vega-lite spec
    if altair.data_transformers.active.startswith("vegafusion"):
        return spec.to_dict(format="vega")  # type: ignore

    # If this is a geoshape, use default transformer
    # since ours does not support geoshapes
    if _has_geoshape(spec):
        with altair.data_transformers.enable("default"):
            return spec.to_dict()  # type: ignore

    with altair.data_transformers.enable("marimo"):
        return spec.to_dict()  # type: ignore


def _has_transforms(spec: VegaSpec) -> bool:
    """Return True if the spec has transforms."""
    return "transform" in spec and len(spec["transform"]) > 0


@mddoc
class altair_chart(UIElement[ChartSelection, ChartDataType]):
    """Make reactive charts with Altair

    Use `mo.ui.altair_chart` to make Altair charts reactive: select chart data
    with your cursor on the frontend, get them as a dataframe in Python!

    For Polars DataFrames, you can convert to a DataFrame.
    However the returned DataFrame will still be a DataFrame,
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

    - `value`: a dataframe of the plot data filtered by the selections
    - `dataframe`: a dataframe of the unfiltered chart data
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
        on_change: Optional[Callable[[ChartDataType], None]] = None,
    ) -> None:
        DependencyManager.altair.require(why="to use `mo.ui.altair_chart`")

        import altair as alt

        register_transformers()

        self._chart = chart

        if not isinstance(chart, (alt.TopLevelMixin)):
            raise ValueError(
                "Invalid type for chart: "
                f"{type(chart)}; expected altair.Chart"
            )

        # Make full-width if no width is specified
        chart = maybe_make_full_width(chart)

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
        if _has_geoshape(vega_spec) and (has_chart_selection):
            sys.stderr.write(
                "Geoshapes + chart selection is not yet supported in "
                "marimo.ui.chart.\n"
                "If you'd like this feature, please file an issue: "
                "https://github.com/marimo-team/marimo/issues\n"
            )
            chart_selection = False

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
    ) -> Union[ChartDataType, altair.UndefinedType]:
        if not isinstance(chart.data, str):
            return chart.data

        if DependencyManager.pandas.imported():
            import pandas as pd

            if chart.data.endswith(".csv"):
                return pd.read_csv(chart.data)
            if chart.data.endswith(".json"):
                return pd.read_json(chart.data)

        if DependencyManager.polars.imported():
            import polars as pl

            if chart.data.startswith("http"):
                import urllib.request

                with urllib.request.urlopen(chart.data) as response:
                    if chart.data.endswith(".csv"):
                        return pl.read_csv(response)
                    if chart.data.endswith(".json"):
                        return pl.read_json(response)

            if chart.data.endswith(".csv"):
                return pl.read_csv(chart.data)
            if chart.data.endswith(".json"):
                return pl.read_json(chart.data)

        return chart.data

    def _convert_value(self, value: ChartSelection) -> Any:
        from altair import Undefined

        self._chart_selection = value
        flat, _ = flatten.flatten(value)
        if not value or not flat:
            if DependencyManager.pandas.imported():
                import pandas as pd

                if isinstance(self.dataframe, pd.DataFrame):
                    return pd.DataFrame()

            if DependencyManager.polars.imported():
                import polars as pl

                if isinstance(self.dataframe, pl.DataFrame):
                    return pl.DataFrame()

            return []

        # When using layered charts, you can no longer access the
        # chart data directly
        # Instead, we should push user to call .apply_selection(df)
        if self.dataframe is Undefined:
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

    def apply_selection(self, df: ChartDataType) -> ChartDataType:
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

        - `df`: a DataFrame to apply the selection to

        **Returns.**

        - a DataFrame of the plot data filtered by the selections
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
    def value(self) -> ChartDataType:
        from altair import Undefined

        value = super().value
        if value is Undefined:
            sys.stderr.write(
                "The underlying chart data is not available in layered"
                " or stacked charts. "
                "Use `.apply_selection(df)` to filter a DataFrame"
                " based on the selection.",
            )
        return value

    @value.setter
    def value(self, value: ChartDataType) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")


def maybe_make_full_width(chart: altair.Chart) -> altair.Chart:
    import altair

    try:
        if (
            isinstance(chart, (altair.Chart, altair.LayerChart))
            and chart.width is altair.Undefined
        ):
            return chart.properties(width="container")
        return chart
    except Exception:
        LOGGER.exception(
            "Failed to set width to full container. "
            "This is likely due to a missing dependency or an invalid chart."
        )
        return chart
