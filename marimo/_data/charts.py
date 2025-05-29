# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import time
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

import narwhals.stable.v1 as nw

from marimo._data.models import DataType
from marimo._utils import assert_never
from marimo._utils.narwhals_utils import can_narwhalify

if TYPE_CHECKING:
    import altair as alt


@abc.abstractmethod
class ChartBuilder:
    @abc.abstractmethod
    def altair(self, data: Any, column: str) -> Any:
        raise NotImplementedError

    def altair_json(self, data: Any, column: str) -> str:
        import altair as alt

        if alt.data_transformers.active.startswith("vegafusion"):
            return cast(str, self.altair(data, column).to_json(format="vega"))
        else:
            return cast(str, self.altair(data, column).to_json())

    @abc.abstractmethod
    def altair_code(self, data: str, column: str, simple: bool) -> str:
        """If simple, return simple altair code."""
        raise NotImplementedError


@dataclass
class ChartParams:
    table_name: str
    column: str


# Comma grouping and no decimals
TOOLTIP_COUNT_FORMAT = ",.0f"

# Comma grouping and 2 decimals
TOOLTIP_NUMBER_FORMAT = ",.2f"

# Percentage with 2 decimals
TOOLTIP_PERCENTAGE_FORMAT = ".2%"

NUM_RECORDS = "Number of records"

# https://www.radix-ui.com/colors/docs/palette-composition/scales
DATE_COLOR = "#2a7e3b"  # grass-11
STRING_COLOR = "#8ec8f6"  # blue-7
BOOLEAN_COLOR = {"scheme": "category10"}
NUMBER_COLOR = "#be93e4"  # purple-8
NUMBER_STROKE = "#8e4ec6"  # purple-9

# Set width to container and remove border lines of chart
COMMON_CONFIG = 'properties(width="container").configure_view(stroke=None)'


def add_common_config(chart: alt.Chart | alt.LayerChart) -> alt.Chart:
    return chart.properties(width="container").configure_view(stroke=None)  # type: ignore


class NumberChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        chart = (
            alt.Chart(data)
            .mark_bar(color=NUMBER_COLOR, stroke=NUMBER_STROKE)
            .encode(
                x=alt.X(column, type="quantitative", bin=True, title=column),
                y=alt.Y("count()", type="quantitative", title=NUM_RECORDS),
                tooltip=[
                    alt.Tooltip(
                        column,
                        type="quantitative",
                        bin=True,
                        title=column,
                        format=TOOLTIP_NUMBER_FORMAT,
                    ),
                    alt.Tooltip(
                        "count()",
                        type="quantitative",
                        format=TOOLTIP_COUNT_FORMAT,
                        title=NUM_RECORDS,
                    ),
                ],
            )
        )
        return add_common_config(chart)

    def altair_code(self, data: str, column: str, simple: bool) -> str:
        mark_bar = (
            """.mark_bar()"""
            if simple
            else """.mark_bar(color="{NUMBER_COLOR}", stroke="{NUMBER_STROKE}")"""
        )

        return f"""
        _chart = (
            alt.Chart({data})
            {mark_bar}
            .encode(
                x=alt.X("{column}", type="quantitative", bin=True, title="{column}"),
                y=alt.Y("count()", type="quantitative", title="{NUM_RECORDS}"),
                tooltip=[
                    alt.Tooltip(
                        "{column}",
                        type="quantitative",
                        bin=True,
                        title="{column}",
                        format="{TOOLTIP_NUMBER_FORMAT}",
                    ),
                    alt.Tooltip(
                        "count()",
                        type="quantitative",
                        format="{TOOLTIP_COUNT_FORMAT}",
                        title="{NUM_RECORDS}",
                    ),
                ],
            ).{COMMON_CONFIG}
        )
        _chart
        """


class StringChartBuilder(ChartBuilder):
    def __init__(self, should_limit_to_10_items: bool) -> None:
        self.should_limit_to_10_items = should_limit_to_10_items
        super().__init__()

    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        _base_chart = (
            alt.Chart(data)
            .transform_aggregate(count="count()", groupby=[column])
            .transform_window(
                rank="rank()",
                sort=[
                    alt.SortField("count", order="descending"),
                    alt.SortField(column, order="ascending"),
                ],
            )
            .transform_joinaggregate(total_count="sum(count)")
            .transform_calculate(percentage="datum.count / datum.total_count")
            .encode(
                y=alt.Y(
                    f"{column}:N",
                    sort="-x",
                    axis=alt.Axis(title=None),
                ),
                x=alt.X("count:Q", title=NUM_RECORDS),
                tooltip=[
                    alt.Tooltip(f"{column}:N"),
                    alt.Tooltip(
                        "count:Q",
                        format=TOOLTIP_COUNT_FORMAT,
                        title=NUM_RECORDS,
                    ),
                ],
            )
        )

        def add_encodings(chart: alt.Chart) -> alt.Chart:
            _bar_chart = chart.mark_bar(color=STRING_COLOR)
            _text_chart = chart.mark_text(align="left", dx=3).encode(
                text=alt.Text("percentage:Q", format=TOOLTIP_PERCENTAGE_FORMAT)
            )
            return _bar_chart + _text_chart  # type: ignore

        if self.should_limit_to_10_items:
            _base_chart = _base_chart.transform_filter(alt.datum.rank <= 10)
            title = f"Top 10 {column}"
        else:
            title = column

        _chart = add_encodings(_base_chart)
        return (
            _chart.properties(title=title, width="container")
            .configure_view(stroke=None)
            .configure_axis(grid=False)
        )

    def altair_code(self, data: str, column: str, simple: bool) -> str:
        return (
            self.simple_altair_code(data, column)
            if simple
            else self.complex_altair_code(data, column)
        )

    def simple_altair_code(self, data: str, column: str) -> str:
        properties_config = (
            """.properties(title="Top 10 {column}", width="container")"""
            if self.should_limit_to_10_items
            else """.properties(width="container")"""
        )

        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .transform_aggregate(count="count()", groupby=["{column}"])
            .transform_window(
                rank="rank()",
                sort=[
                    alt.SortField("count", order="descending"),
                    alt.SortField("{column}", order="ascending"),
                ],
            )
            .transform_filter(alt.datum.rank <= 10)
            .encode(
                y=alt.Y(
                    "{column}:N",
                    sort="-x",
                    axis=alt.Axis(title=None),
                ),
                x=alt.X("count:Q", title="{NUM_RECORDS}"),
                tooltip=[
                    alt.Tooltip("{column}:N"),
                    alt.Tooltip("count:Q", format="{TOOLTIP_COUNT_FORMAT}", title="{NUM_RECORDS}"),
                ],
            )
            {properties_config}
            .configure_view(stroke=None)
            .configure_axis(grid=False)
        )
        _chart
        """

    def complex_altair_code(self, data: str, column: str) -> str:
        base_chart_code = dedent(f"""
        _base_chart = (
            alt.Chart({data})
            .transform_aggregate(count="count()", groupby=["{column}"])
            .transform_window(
                rank="rank()",
                sort=[
                    alt.SortField("count", order="descending"),
                    alt.SortField("{column}", order="ascending"),
                ],
            )
            .transform_filter(alt.datum.rank <= 10)
            .transform_joinaggregate(total_count="sum(count)")
            .transform_calculate(
                percentage="datum.count / datum.total_count"
            )
            .encode(
                y=alt.Y(
                    "{column}:N",
                    sort="-x",
                    axis=alt.Axis(title=None),
                ),
                x=alt.X("count:Q", title="{NUM_RECORDS}"),
                tooltip=[
                    alt.Tooltip("{column}:N"),
                    alt.Tooltip("count:Q", format="{TOOLTIP_COUNT_FORMAT}", title="{NUM_RECORDS}"),
                ],
            )
        )

        _bar_chart = _base_chart.mark_bar(color="{STRING_COLOR}")
        _text_chart = _base_chart.mark_text(align="left", dx=3).encode(
            text=alt.Text("percentage:Q", format="{TOOLTIP_PERCENTAGE_FORMAT}")
        )
        """)

        if self.should_limit_to_10_items:
            return f"""
            {base_chart_code}
_chart = (
    (_bar_chart + _text_chart)
    .properties(title="Top 10 {column}", width="container")
    .configure_view(stroke=None)
    .configure_axis(grid=False)
)
_chart
            """

        return f"""
        {base_chart_code}
_chart = (
    (_bar_chart + _text_chart)
    .properties(width="container")
    .configure_view(stroke=None)
    .configure_axis(grid=False)
)
_chart
        """


TimeUnitOptions = Literal[
    "year",
    "month",
    "date",
    "yearmonth",
    "yearmonthdate",
    "monthdate",
    "yearmonthdatehours",
    "yearmonthdatehoursminutes",
    "hoursminutesseconds",
]


class DateChartBuilder(ChartBuilder):
    DEFAULT_DATE_FORMAT = "%Y-%m-%d"
    DEFAULT_TIME_UNIT: TimeUnitOptions = "yearmonthdate"

    def __init__(self) -> None:
        self.date_format: Optional[str] = None
        self.time_unit: Optional[TimeUnitOptions] = None

    def _guess_date_format(
        self, data: Any, column: str
    ) -> tuple[str, TimeUnitOptions]:
        """
        Guess the appropriate date format based on the range of dates in the column.
        Returns date_format, time_unit
        """
        if not can_narwhalify(data, eager_only=True):
            return self.DEFAULT_DATE_FORMAT, self.DEFAULT_TIME_UNIT

        df = nw.from_native(data, eager_only=True)

        # Get min and max dates using narwhals
        min_date = df[column].min()
        max_date = df[column].max()

        # Handle time-only data
        if isinstance(min_date, time) and isinstance(max_date, time):
            return "%H:%M:%S", "hoursminutesseconds"

        # Calculate the difference in days
        time_diff = max_date - min_date
        if not hasattr(time_diff, "days"):
            return self.DEFAULT_DATE_FORMAT, self.DEFAULT_TIME_UNIT

        days_diff = time_diff.days

        # Choose format based on the range
        if days_diff > 365 * 10:  # More than 10 years
            return "%Y", "year"  # Year only
        elif days_diff > 365:  # More than a year
            return "%Y-%m", "yearmonth"  # Year and month
        elif days_diff > 31:  # More than a month
            return "%Y-%m-%d", "yearmonthdate"  # Full date
        elif days_diff > 1:  # More than a day
            return "%Y-%m-%d %H", "yearmonthdatehours"  # Date and time (hours)
        else:
            # Date and time (hours, minutes)
            return (
                "%Y-%m-%d %H:%M",
                "yearmonthdatehoursminutes",
            )

    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        _, time_unit = self._guess_date_format(data, column)
        # Time only charts don't work properly

        new_field = f"date_{column}"

        base = alt.Chart(data).transform_filter(f"datum.{column} != null")

        # Explicit time binning, create a new field
        transformed = base.transform_timeunit(
            as_=new_field, field=column, timeUnit=time_unit
        ).transform_aggregate(count="count()", groupby=[new_field])

        # Create a selection that picks the nearest points
        nearest = alt.selection_point(
            fields=[new_field], nearest=True, on="mouseover", empty=False
        )

        # Area chart
        area = transformed.mark_area(
            line={"color": DATE_COLOR},
            color=alt.Gradient(
                gradient="linear",  # type: ignore
                stops=[
                    alt.GradientStop(color="white", offset=0),
                    alt.GradientStop(color=DATE_COLOR, offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
        ).encode(
            x=alt.X(f"{new_field}:T", title=column),
            y=alt.Y("count:Q", title=NUM_RECORDS),
        )

        # Vertical line
        rule = (
            transformed.mark_rule(color="seagreen", strokeWidth=1)
            .encode(
                x=f"{new_field}:T",
                opacity=alt.condition(nearest, alt.value(0.6), alt.value(0)),
                tooltip=[
                    alt.Tooltip(
                        f"{new_field}:T",
                        title=column,
                        timeUnit=time_unit,
                    ),
                    alt.Tooltip(
                        "count:Q",
                        title=NUM_RECORDS,
                        format=TOOLTIP_COUNT_FORMAT,
                    ),
                ],
            )
            .add_params(nearest)
        )

        # Points on the chart
        points = transformed.mark_point(
            size=80,
            color=DATE_COLOR,
            filled=True,
        ).encode(
            x=f"{new_field}:T",
            y="count:Q",
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
        )

        chart = add_common_config(alt.layer(area, points, rule))
        return chart

    def altair_code(self, data: str, column: str, simple: bool = True) -> str:
        return (
            self.simple_altair_code(data, column)
            if simple
            else self.complex_altair_code(data, column)
        )

    def simple_altair_code(self, data: str, column: str) -> str:
        """Offer simple charts for users to copy"""
        _, time_unit = self._guess_date_format(data, column)
        new_field = f"_{column}"

        return f"""
        _chart = (
            alt.Chart({data})
            .transform_filter(f"datum.{column} != null")
            .transform_timeunit(as_="{new_field}", field="{column}", timeUnit="{time_unit}")
            .mark_area()
            .encode(
                x=alt.X("{new_field}:T", title="{column}"),
                y=alt.Y("count():Q", title="{NUM_RECORDS}"),
                tooltip=[
                    alt.Tooltip("{new_field}:T", title="{column}", timeUnit="{time_unit}"),
                    alt.Tooltip("count():Q", title="{NUM_RECORDS}", format="{TOOLTIP_COUNT_FORMAT}")
                ]
            ).{COMMON_CONFIG}
        )
        _chart
        """

    def complex_altair_code(self, data: str, column: str) -> str:
        """Complex altair code for data charts. Offer more control over the chart"""
        _, time_unit = self._guess_date_format(data, column)

        new_field = f"_{column}"

        return f"""
        _base = alt.Chart({data}).transform_filter(f"datum.{column} != null")

        # Explicit time binning, create a new field
        _transformed = _base.transform_timeunit(
            as_="{new_field}", field="{column}", timeUnit="{time_unit}"
        ).transform_aggregate(count="count()", groupby=["{new_field}"])

        # Create a selection that picks the nearest points
        _nearest = alt.selection_point(
            fields=["{new_field}"],
            nearest=True,
            on="mouseover",
            empty=False,
        )

        # Area chart
        _area = _transformed.mark_area(
            line={{"color": "{DATE_COLOR}"}},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="white", offset=0),
                    alt.GradientStop(color="{DATE_COLOR}", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
        ).encode(
            x=alt.X("{new_field}:T", title="{column}"),
            y=alt.Y("count:Q", title="{NUM_RECORDS}"),
        )

        # Vertical line
        _rule = (
            _transformed.mark_rule(color="seagreen", strokeWidth=1)
            .encode(
                x="{new_field}:T",
                opacity=alt.condition(_nearest, alt.value(0.6), alt.value(0)),
                tooltip=[
                    alt.Tooltip(
                        "{new_field}:T",
                        title="{column}",
                        timeUnit="{time_unit}",
                    ),
                    alt.Tooltip(
                        "count:Q",
                        title="{NUM_RECORDS}",
                        format="{TOOLTIP_COUNT_FORMAT}",
                    ),
                ],
            )
            .add_params(_nearest)
        )

        # Points on the chart
        _points = _transformed.mark_point(
            size=80,
            color="{DATE_COLOR}",
            filled=True,
        ).encode(
            x="{new_field}:T",
            y="count:Q",
            opacity=alt.condition(_nearest, alt.value(1), alt.value(0)),
        )

        _chart = alt.layer(_area, _points, _rule).{COMMON_CONFIG}
        _chart
        """


class BooleanChartBuilder(ChartBuilder):
    PIE_RADIUS = 85
    TEXT_RADIUS = 110
    TEXT_SIZE = 13

    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        base = (
            alt.Chart(data)
            .transform_aggregate(count="count()", groupby=[column])
            .transform_joinaggregate(total="sum(count)")
            .transform_calculate(percentage="datum.count / datum.total")
            .encode(
                theta=alt.Theta(
                    field="count",
                    type="quantitative",
                    stack=True,
                ),
                color=alt.Color(
                    f"{column}:N",
                    scale=BOOLEAN_COLOR,
                    legend=alt.Legend(title=column),
                ),
                tooltip=[
                    alt.Tooltip(f"{column}:N", title=column),
                    alt.Tooltip(
                        "count:Q",
                        title=NUM_RECORDS,
                        format=TOOLTIP_COUNT_FORMAT,
                    ),
                ],
            )
        )

        pie = base.mark_arc(outerRadius=self.PIE_RADIUS)
        text = base.mark_text(
            radius=self.TEXT_RADIUS, size=self.TEXT_SIZE
        ).encode(
            text=alt.Text("percentage:Q", format=TOOLTIP_PERCENTAGE_FORMAT)
        )

        return (pie + text).properties(width="container")

    def altair_code(self, data: str, column: str, simple: bool) -> str:
        return (
            self.simple_altair_code(data, column)
            if simple
            else self.complex_altair_code(data, column)
        )

    def complex_altair_code(self, data: str, column: str) -> str:
        return f"""
        _base = (
            alt.Chart({data})
            .transform_aggregate(
                count="count()",
                groupby=["{column}"]
            )
            .transform_joinaggregate(
                total="sum(count)"
            )
            .transform_calculate(
                percentage="datum.count / datum.total"
            )
            .encode(
                theta=alt.Theta(
                    field="count",
                    type="quantitative",
                    stack=True,
                ),
                color=alt.Color(
                    "{column}:N",
                    scale={BOOLEAN_COLOR},
                    legend=alt.Legend(title="{column}")
                ),
                tooltip=[
                    alt.Tooltip("{column}:N", title="{column}"),
                    alt.Tooltip("count:Q", title="{NUM_RECORDS}", format="{TOOLTIP_COUNT_FORMAT}"),
                ],
            )
        )

        _pie = _base.mark_arc(outerRadius={self.PIE_RADIUS})
        _text = _base.mark_text(radius={self.TEXT_RADIUS}, size={self.TEXT_SIZE}).encode(
            text=alt.Text("percentage:Q", format="{TOOLTIP_PERCENTAGE_FORMAT}"),
        )

        _chart = (_pie + _text).properties(width="container")
        _chart
        """

    def simple_altair_code(self, data: str, column: str) -> str:
        """Removed colours"""

        return f"""
        _base = (
            alt.Chart({data})
            .transform_aggregate(count="count()", groupby=["{column}"])
            .transform_joinaggregate(total="sum(count)")
            .transform_calculate(percentage="datum.count / datum.total")
            .encode(
                theta=alt.Theta(
                    field="count",
                    type="quantitative",
                    stack=True,
                ),
                color=alt.Color("{column}:N"),
                tooltip=[
                    alt.Tooltip("{column}:N", title="{column}"),
                    alt.Tooltip("count:Q", title="{NUM_RECORDS}", format="{TOOLTIP_COUNT_FORMAT}"),
                ],
            )
        )

        _pie = _base.mark_arc(outerRadius={self.PIE_RADIUS})
        _text = _base.mark_text(radius={self.TEXT_RADIUS}, size={self.TEXT_SIZE}).encode(
            text=alt.Text("percentage:Q", format="{TOOLTIP_PERCENTAGE_FORMAT}"),
        )

        _chart = (_pie + _text).{COMMON_CONFIG}
        _chart
        """


class IntegerChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        chart = (
            alt.Chart(data)
            .mark_bar(color=NUMBER_COLOR, stroke=NUMBER_STROKE)
            .encode(
                x=alt.X(column, type="quantitative", bin=True, title=column),
                y=alt.Y("count()", type="quantitative", title=NUM_RECORDS),
                tooltip=[
                    alt.Tooltip(
                        column, type="quantitative", bin=True, title=column
                    ),
                    alt.Tooltip(
                        "count()",
                        type="quantitative",
                        format=TOOLTIP_COUNT_FORMAT,
                        title=NUM_RECORDS,
                    ),
                ],
            )
        )
        return add_common_config(chart)

    def altair_code(self, data: str, column: str, simple: bool = True) -> str:
        mark_bar = (
            """.mark_bar()"""
            if simple
            else """.mark_bar(color="{NUMBER_COLOR}", stroke="{NUMBER_STROKE}")"""
        )

        return f"""
        _chart = (
            alt.Chart({data})
            {mark_bar}
            .encode(
                x=alt.X("{column}", type="quantitative", bin=True, title="{column}"),
                y=alt.Y("count()", type="quantitative", title="{NUM_RECORDS}"),
                tooltip=[
                    alt.Tooltip(
                        "{column}",
                        type="quantitative",
                        bin=True,
                        title="{column}",
                    ),
                    alt.Tooltip(
                        "count()",
                        type="quantitative",
                        format="{TOOLTIP_COUNT_FORMAT}",
                        title="{NUM_RECORDS}",
                    ),
                ],
            ).{COMMON_CONFIG}
        )
        _chart
        """


class UnknownChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        chart = (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="nominal"),
                y=alt.Y("count()", type="quantitative", title=NUM_RECORDS),
                tooltip=[
                    alt.Tooltip(column, type="nominal"),
                    alt.Tooltip(
                        "count()", type="quantitative", title=NUM_RECORDS
                    ),
                ],
            )
        )
        return add_common_config(chart)

    def altair_code(self, data: str, column: str, _simple: bool = True) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="nominal"),
                y=alt.Y("count()", type="quantitative", title="{NUM_RECORDS}"),
                tooltip=[
                    alt.Tooltip("{column}", type="nominal"),
                    alt.Tooltip("count()", type="quantitative", title="{NUM_RECORDS}"),
                ],
            ).{COMMON_CONFIG}
        )
        _chart
        """


class WrapperChartBuilder(ChartBuilder):
    def __init__(self, delegate: ChartBuilder):
        self.delegate = delegate

    def altair(self, data: Any, column: str) -> Any:
        return self.delegate.altair(
            data, _escape_special_path_characters(str(column))
        )

    def altair_code(self, data: str, column: str, simple: bool = True) -> str:
        return dedent(
            self.delegate.altair_code(
                data, _escape_special_path_characters(str(column)), simple
            )
        ).strip()


def get_chart_builder(
    column_type: DataType, should_limit_to_10_items: bool = False
) -> ChartBuilder:
    if column_type == "number":
        return WrapperChartBuilder(NumberChartBuilder())
    if column_type == "string":
        return WrapperChartBuilder(
            StringChartBuilder(should_limit_to_10_items)
        )
    if (
        column_type == "date"
        or column_type == "datetime"
        or column_type == "time"
    ):
        return WrapperChartBuilder(DateChartBuilder())
    if column_type == "boolean":
        return WrapperChartBuilder(BooleanChartBuilder())
    if column_type == "integer":
        return WrapperChartBuilder(IntegerChartBuilder())
    if column_type == "unknown":
        return WrapperChartBuilder(UnknownChartBuilder())

    assert_never(column_type)


def _escape_special_path_characters(column: str | int) -> str:
    """
    Escape special characters in a column name that is a path.
    """
    if not isinstance(column, str):
        return str(column)

    return (
        column.replace(".", "\\.")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(":", "\\:")
    )
