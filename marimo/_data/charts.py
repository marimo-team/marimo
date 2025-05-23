# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Literal, Optional, cast

import narwhals.stable.v1 as nw

from marimo._data.models import DataType
from marimo._utils import assert_never
from marimo._utils.narwhals_utils import can_narwhalify


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
    def altair_code(self, data: str, column: str) -> str:
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


class NumberChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="quantitative", bin=True, title=column),
                y=alt.Y("count()", type="quantitative"),
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
                    ),
                ],
            )
            .properties(width="container")
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="quantitative", bin=True, title="{column}"),
                y=alt.Y("count()", type="quantitative"),
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
                    ),
                ],
            )
            .properties(width="container")
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
                x=alt.X("count:Q"),
                tooltip=[
                    alt.Tooltip(f"{column}:N"),
                    alt.Tooltip("count:Q", format=TOOLTIP_COUNT_FORMAT),
                ],
            )
        )

        def add_encodings(chart: alt.Chart) -> alt.Chart:
            _bar_chart = chart.mark_bar()
            _text_chart = chart.mark_text(align="left", dx=3).encode(
                text=alt.Text("percentage:Q", format=TOOLTIP_PERCENTAGE_FORMAT)
            )
            return _bar_chart + _text_chart

        if self.should_limit_to_10_items:
            _base_chart = _base_chart.transform_filter(alt.datum.rank <= 10)
            _chart = add_encodings(_base_chart)
            return (
                _chart.properties(title=f"Top 10 {column}", width="container")
                .configure_view(stroke=None)
                .configure_axis(grid=False)
            )

        _chart = add_encodings(_base_chart)
        return (
            _chart.properties(width="container")
            .configure_view(stroke=None)
            .configure_axis(grid=False)
        )

    def altair_code(self, data: str, column: str) -> str:
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
                x=alt.X("count:Q"),
                tooltip=[
                    alt.Tooltip("{column}:N"),
                    alt.Tooltip("count:Q", format="{TOOLTIP_COUNT_FORMAT}"),
                ],
            )
        )

        _bar_chart = _base_chart.mark_bar()
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
]


class DateChartBuilder(ChartBuilder):
    DEFAULT_DATE_FORMAT = "%Y-%m-%d"
    DEFAULT_TIME_UNIT: TimeUnitOptions = "yearmonthdate"

    def __init__(self) -> None:
        self.date_format: Optional[str] = None
        self.time_unit: Optional[TimeUnitOptions] = None
        self.base_color = "darkgreen"

    def _get_date_format(
        self, data: Any, column: str
    ) -> tuple[str, TimeUnitOptions]:
        if self.date_format is not None and self.time_unit is not None:
            return self.date_format, self.time_unit
        else:
            date_format, time_unit = self._guess_date_format(data, column)
            # Set the date format and time unit to avoid recalculating
            self.date_format = str(date_format)
            self.time_unit = time_unit
            return date_format, time_unit

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

        date_format, time_unit = self._get_date_format(data, column)
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
            line={"color": self.base_color},
            color=alt.Gradient(
                gradient="linear",  # type: ignore
                stops=[
                    alt.GradientStop(color="white", offset=0),
                    alt.GradientStop(color=self.base_color, offset=1),
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
            color=self.base_color,
            filled=True,
        ).encode(
            x=f"{new_field}:T",
            y="count:Q",
            opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
        )

        chart = alt.layer(area, points, rule).properties(width="container")
        return chart

    def altair_code(self, data: str, column: str) -> str:
        _date_format, time_unit = self._get_date_format(data, column)

        new_field = f"_{column}"
        formatted_field = f'"{new_field}"'
        formatted_field_with_type = f'"{new_field}:T"'
        time_unit_str = f'"{time_unit}"'

        return f"""
        _base = alt.Chart({data}).transform_filter(f"datum.{column} != null")

        # Explicit time binning, create a new field
        _transformed = _base.transform_timeunit(
            as_={formatted_field}, field="{column}", timeUnit={time_unit_str}
        ).transform_aggregate(count="count()", groupby=[{formatted_field}])

        # Create a selection that picks the nearest points
        _nearest = alt.selection_point(
            fields=[{formatted_field}],
            nearest=True,
            on="mouseover",
            empty=False,
        )

        # Area chart
        _area = _transformed.mark_area(
            line={{"color": "{self.base_color}"}},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="white", offset=0),
                    alt.GradientStop(color="{self.base_color}", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
        ).encode(
            x=alt.X({formatted_field_with_type}, title="{column}"),
            y=alt.Y("count:Q", title="{NUM_RECORDS}"),
        )

        # Vertical line
        _rule = (
            _transformed.mark_rule(color="seagreen", strokeWidth=1)
            .encode(
                x={formatted_field_with_type},
                opacity=alt.condition(_nearest, alt.value(0.6), alt.value(0)),
                tooltip=[
                    alt.Tooltip(
                        {formatted_field_with_type},
                        title="{column}",
                        timeUnit={time_unit_str},
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
            color="{self.base_color}",
            filled=True,
        ).encode(
            x={formatted_field_with_type},
            y="count:Q",
            opacity=alt.condition(_nearest, alt.value(1), alt.value(0)),
        )

        _chart = alt.layer(_area, _points, _rule).properties(width="container")
        _chart
        """


class BooleanChartBuilder(ChartBuilder):
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
                    scale={"scheme": "category10"},
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

        pie = base.mark_arc(outerRadius=85)
        text = base.mark_text(radius=100, size=13).encode(
            text=alt.Text("percentage:Q", format=TOOLTIP_PERCENTAGE_FORMAT)
        )

        return (pie + text).properties(width="container")

    def altair_code(self, data: str, column: str) -> str:
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
                    scale={{"scheme": "category10"}},
                    legend=alt.Legend(title="{column}")
                ),
                tooltip=[
                    alt.Tooltip("{column}:N", title="{column}"),
                    alt.Tooltip("count:Q", title="{NUM_RECORDS}", format="{TOOLTIP_COUNT_FORMAT}"),
                ],
            )
        )

        _pie = _base.mark_arc(outerRadius=85)
        _text = _base.mark_text(radius=100, size=13).encode(
            text=alt.Text("percentage:Q", format="{TOOLTIP_PERCENTAGE_FORMAT}"),
        )

        _chart = (_pie + _text).properties(width="container")
        _chart
        """


class IntegerChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="quantitative", bin=True, title=column),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip(
                        column, type="quantitative", bin=True, title=column
                    ),
                    alt.Tooltip(
                        "count()",
                        type="quantitative",
                        format=TOOLTIP_COUNT_FORMAT,
                    ),
                ],
            )
            .properties(width="container")
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="quantitative", bin=True, title="{column}"),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip(
                        "{column}",
                        type="quantitative",
                        bin=True,
                        title="{column}",
                    ),
                    alt.Tooltip(
                        "count()", type="quantitative", format="{TOOLTIP_COUNT_FORMAT}",
                    ),
                ],
            )
            .properties(width="container")
        )
        _chart
        """


class UnknownChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="nominal"),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip(column, type="nominal"),
                    alt.Tooltip("count()", type="quantitative"),
                ],
            )
            .properties(width="container")
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="nominal"),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip("{column}", type="nominal"),
                    alt.Tooltip("count()", type="quantitative"),
                ],
            )
            .properties(width="container")
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

    def altair_code(self, data: str, column: str) -> str:
        return dedent(
            self.delegate.altair_code(
                data, _escape_special_path_characters(str(column))
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
