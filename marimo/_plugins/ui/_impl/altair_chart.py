# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Literal,
    Optional,
    Union,
    cast,
)

import narwhals.stable.v1 as nw
from narwhals.typing import IntoDataFrame

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.charts.altair_transformer import (
    register_transformers,
)
from marimo._utils import flatten
from marimo._utils.narwhals_utils import (
    assert_can_narwhalify,
    can_narwhalify,
    empty_df,
)

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import altair
    import altair.vegalite

# Selection is a dictionary of the form:
# {
#   "signal_channel": {
#     "field": ["value1", "value2", ...]
#   }
# }
ChartSelectionField = dict[str, Union[list[int], list[float], list[str]]]
ChartSelection = dict[str, ChartSelectionField]
VegaSpec = dict[str, Any]
RowOrientedData = list[dict[str, Any]]
ColumnOrientedData = dict[str, list[Any]]

ChartDataType = Union[IntoDataFrame, RowOrientedData, ColumnOrientedData]

# Union of all possible chart types
AltairChartType: TypeAlias = "altair.vegalite.v5.api.ChartType"


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
            # Check for nested layers, vconcat, hconcat
            if hasattr(spec, "layer"):
                return any(_has_geoshape(layer) for layer in spec.layer)
            if hasattr(spec, "vconcat"):
                return any(_has_geoshape(layer) for layer in spec.vconcat)
            if hasattr(spec, "hconcat"):
                return any(_has_geoshape(layer) for layer in spec.hconcat)
            return False
        mark = spec.mark  # type: ignore
        return mark == "geoshape" or mark.type == "geoshape"  # type: ignore
    except Exception:
        return False


def _using_vegafusion() -> bool:
    """Return True if the current data transformer is vegafusion."""
    import altair

    return altair.data_transformers.active.startswith("vegafusion")  # type: ignore


def _filter_dataframe(
    native_df: IntoDataFrame, selection: ChartSelection
) -> IntoDataFrame:
    df = nw.from_native(native_df)
    if not isinstance(selection, dict):
        raise TypeError("Input 'selection' must be a dictionary")

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
            vgsid = fields.get("_vgsid_", [])
            try:
                indexes = [int(i) - 1 for i in vgsid]
                df = cast(nw.DataFrame[Any], df)[indexes]
            except IndexError:
                # Out of bounds index, return empty dataframe if it's the
                df = cast(nw.DataFrame[Any], df)[[]]
                LOGGER.error(f"Invalid index in selection: {vgsid}")
            except ValueError:
                LOGGER.error(f"Invalid index in selection: {vgsid}")
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
            resolved_values = _resolve_values(values, dtype)
            if is_point_selection:
                df = df.filter(nw.col(field).is_in(resolved_values))
            elif len(resolved_values) == 1:
                df = df.filter(nw.col(field) == resolved_values[0])
            # Range selection
            elif len(resolved_values) == 2 and _is_numeric_or_date(
                resolved_values[0]
            ):
                left_value, right_value = resolved_values
                df = df.filter(
                    (nw.col(field) >= left_value)
                    & (nw.col(field) <= right_value)
                )
            # Multi-selection via range
            # This can happen when you use an interval selection
            # on categorical data
            elif len(resolved_values) > 1:
                df = df.filter(nw.col(field).is_in(resolved_values))
            else:
                raise ValueError(
                    f"Invalid selection: {field}={resolved_values}"
                )

    return nw.to_native(df)


def _resolve_values(values: Any, dtype: Any) -> list[Any]:
    def _coerce_value(value: Any, dtype: Any) -> Any:
        import zoneinfo

        if nw.Date == dtype:
            if isinstance(value, str):
                return datetime.date.fromisoformat(value)
            # Value is milliseconds since epoch
            # so we convert to seconds since epoch
            return datetime.date.fromtimestamp(value / 1000)
        if nw.Datetime == dtype and isinstance(dtype, nw.Datetime):
            if isinstance(value, str):
                res = datetime.datetime.fromisoformat(value)
                # If dtype has no timezone, shift by local timezone offset
                if dtype.time_zone is None:
                    local_tz = datetime.datetime.now().astimezone().tzinfo
                    LOGGER.warning(
                        f"Datetime was given with a timezone when not expected. "
                        f"Shifting by local timezone offset {local_tz}."
                    )
                    return res.astimezone(local_tz).replace(tzinfo=None)
                return res

            # Value is milliseconds since epoch
            # so we convert to seconds since epoch
            return datetime.datetime.fromtimestamp(
                value / 1000,
                tz=(
                    zoneinfo.ZoneInfo(dtype.time_zone)
                    if dtype.time_zone
                    else None
                ),
            )
        return value

    if isinstance(values, list):
        return [_coerce_value(v, dtype) for v in values]
    return [_coerce_value(values, dtype)]


def _is_numeric_or_date(value: Any) -> bool:
    if isinstance(value, (int, float, datetime.date, datetime.datetime)):
        return True

    if DependencyManager.numpy.imported():
        import numpy as np

        if isinstance(value, np.number):
            return True

    return False


def _parse_spec(spec: altair.TopLevelMixin) -> VegaSpec:
    import altair as alt

    # vegafusion requires creating a vega spec,
    # instead of using a vega-lite spec
    if alt.data_transformers.active.startswith("vegafusion"):
        return spec.to_dict(format="vega")  # type: ignore

    # If this is a geoshape, use default transformer
    # since ours does not support geoshapes
    if _has_geoshape(spec):
        with alt.data_transformers.enable("default"):
            return spec.to_dict()  # type: ignore

    with alt.data_transformers.enable("marimo_arrow"):
        return spec.to_dict(validate=False)  # type: ignore


def _has_transforms(spec: VegaSpec) -> bool:
    """Return True if the spec has transforms."""
    return "transform" in spec and len(spec["transform"]) > 0


@mddoc
class altair_chart(UIElement[ChartSelection, ChartDataType]):
    """Make reactive charts with Altair.

    Use `mo.ui.altair_chart` to make Altair charts reactive: select chart data
    with your cursor on the frontend, get them as a dataframe in Python!

    Supports polars, pandas, and arrow DataFrames.

    Examples:
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

        ```python
        # View the chart and selected data as a dataframe
        mo.hstack([chart, chart.value])
        ```

    Attributes:
        value (ChartDataType): A dataframe of the plot data filtered by the selections.
        dataframe (ChartDataType): A dataframe of the unfiltered chart data.
        selections (ChartSelection): The selection of the chart; this may be an interval
            along the name of an axis or a selection of points.

    Args:
        chart (altair.Chart): An Altair Chart object.
        chart_selection (Union[Literal["point"], Literal["interval"], bool], optional):
            Selection type, "point", "interval", or a bool. Defaults to True which will
            automatically detect the best selection type. This is ignored if the chart
            already has a point/interval selection param.
        legend_selection (Union[list[str], bool], optional): List of legend fields
            (columns) for which to enable selection, True to enable selection for all
            fields, or False to disable selection entirely. This is ignored if the chart
            already has a legend selection param. Defaults to True.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Optional[Callable[[ChartDataType], None]], optional): Optional
            callback to run when this element's value changes. Defaults to None.
    """

    name: Final[str] = "marimo-vega"

    def __init__(
        self,
        chart: AltairChartType,
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
                f"Invalid type for chart: {type(chart)}; expected altair.Chart"
            )

        # Make full-width if no width is specified
        chart = maybe_make_full_width(chart)

        # Fix the sizing for vconcat charts
        if isinstance(chart, alt.VConcatChart):
            chart = _update_vconcat_width(chart)

            # without autosize, vconcat will overflow
            if chart.autosize is alt.Undefined:
                chart.autosize = "fit-x"

        vega_spec = _parse_spec(chart)

        if label:
            vega_spec["title"] = label

        # Types say this is not possible,
        # but a user still may pass none
        if chart_selection is None:  # type: ignore
            chart_selection = False
        if legend_selection is None:  # type: ignore
            legend_selection = False

        # If the chart already has a selection param,
        # we don't add any more
        if _has_selection_param(chart):
            # Log a warning if the user has set chart_selection
            # but the chart already has a selection param
            if isinstance(chart_selection, str):
                sys.stderr.write(
                    f"Warning: chart already has a selection param. "
                    f"Ignoring chart_selection={chart_selection}"
                )
            chart_selection = False

        if _has_legend_param(chart):
            # Log a warning if the user has set legend_selection
            # but the chart already has a legend param
            if (
                isinstance(legend_selection, list)
                and len(legend_selection) > 0
            ):
                sys.stderr.write(
                    f"Warning: chart already has a legend param. "
                    f"Ignoring legend_selection={legend_selection}"
                )
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
        if _has_geoshape(chart) and (has_chart_selection):
            sys.stderr.write(
                "Geoshapes + chart selection is not yet supported in "
                "marimo.ui.chart.\n"
                "If you'd like this feature, please file an issue: "
                "https://github.com/marimo-team/marimo/issues\n"
            )
            chart_selection = False

        if _using_vegafusion() and (
            has_chart_selection or has_legend_selection
        ):
            chart_selection = False
            legend_selection = False
            sys.stderr.write(
                "Selection is not yet supported while using vegafusion with mo.ui.altair_chart.\n"
                "You can follow the progress here: "
                "https://github.com/marimo-team/marimo/issues/4601"
            )

        self.dataframe: Optional[ChartDataType] = (
            self._get_dataframe_from_chart(chart)
        )

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
        chart: Union[altair.Chart, altair.LayerChart],
    ) -> Optional[ChartDataType]:
        if not isinstance(chart.data, str):
            return cast(ChartDataType, chart.data)

        url = chart.data

        if DependencyManager.polars.imported():
            import polars as pl

            if url.endswith(".csv"):
                return pl.read_csv(url)
            if url.endswith(".json"):
                import urllib.request

                # polars read_json does not support urls
                with urllib.request.urlopen(chart.data) as response:
                    return pl.read_json(response)

        if DependencyManager.pandas.imported():
            import pandas as pd

            if url.endswith(".csv"):
                return pd.read_csv(url)
            if url.endswith(".json"):
                return pd.read_json(url)

        import altair as alt

        if chart.data is alt.Undefined:  # type: ignore[comparison-overlap]
            return None

        return cast(ChartDataType, chart.data)

    def _convert_value(self, value: ChartSelection) -> ChartDataType:
        self._chart_selection = value
        flat, _ = flatten.flatten(value)
        if not value or not flat:
            if self.dataframe is None:
                return []
            if isinstance(self.dataframe, list):
                return []
            if isinstance(self.dataframe, dict):
                return {}
            return empty_df(self.dataframe)

        # When using layered charts, you can no longer access the
        # chart data directly
        # Instead, we should push user to call .apply_selection(df)
        if not can_narwhalify(self.dataframe):
            return self.dataframe  # type: ignore

        # If we have transforms, we need to filter the dataframe
        # with those transforms, before applying the selection
        if _has_transforms(self._spec):
            try:
                df: Any = self._chart.transformed_data()
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

        Args:
            df (ChartDataType): A DataFrame to apply the selection to.

        Returns:
            ChartDataType: A DataFrame of the plot data filtered by the selections.

        Examples:
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
        """
        assert assert_can_narwhalify(df)
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
        if value is Undefined:  # type: ignore
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


def maybe_make_full_width(chart: AltairChartType) -> AltairChartType:
    import altair as alt

    try:
        if (
            isinstance(chart, (alt.Chart, alt.LayerChart))
            and chart.width is alt.Undefined
        ):
            return chart.properties(width="container")
        return chart
    except Exception:
        LOGGER.exception(
            "Failed to set width to full container. "
            "This is likely due to a missing dependency or an invalid chart."
        )
        return chart


def _has_selection_param(chart: AltairChartType) -> bool:
    import altair as alt

    if not hasattr(chart, "params"):
        return False

    try:
        for param in chart.params:  # type: ignore
            try:
                if isinstance(
                    param,
                    (alt.SelectionParameter, alt.TopLevelSelectionParameter),
                ):
                    if param.bind is alt.Undefined:
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _has_legend_param(chart: AltairChartType) -> bool:
    import altair as alt

    if not hasattr(chart, "params"):
        return False

    try:
        for param in chart.params:  # type: ignore
            try:
                if isinstance(
                    param,
                    (alt.SelectionParameter, alt.TopLevelSelectionParameter),
                ):
                    if param.bind == "legend":
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _update_vconcat_width(chart: AltairChartType) -> AltairChartType:
    """Mutate the chart to set the width to the container."""

    import altair as alt

    if isinstance(chart, alt.VConcatChart):
        chart.vconcat = [
            _update_vconcat_width(subchart) for subchart in chart.vconcat
        ]
        return chart  # type: ignore[no-any-return]

    if isinstance(chart, alt.LayerChart):
        chart.layer = [_update_vconcat_width(layer) for layer in chart.layer]
        return chart  # type: ignore[no-any-return]

    if isinstance(chart, alt.HConcatChart):
        chart.hconcat = [
            _update_vconcat_width(subchart) for subchart in chart.hconcat
        ]
        return chart  # type: ignore[no-any-return]

    if isinstance(chart, alt.Chart):
        return maybe_make_full_width(chart)

    # Not handled
    return chart
