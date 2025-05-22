# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, cast

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

        if self.should_limit_to_10_items:
            return (
                alt.Chart(data)
                .transform_aggregate(count="count()", groupby=[column])
                .transform_window(
                    rank="rank()",
                    sort=[
                        alt.SortField("count", order="descending"),
                        alt.SortField(column, order="ascending"),
                    ],
                )
                .transform_filter(alt.datum.rank <= 10)
                .mark_bar()
                .encode(
                    y=alt.Y(column, type="nominal", sort="-x"),
                    x=alt.X("count", type="quantitative"),
                    tooltip=[
                        alt.Tooltip(column, type="nominal"),
                        alt.Tooltip(
                            "count",
                            type="quantitative",
                            format=TOOLTIP_COUNT_FORMAT,
                        ),
                    ],
                )
                .properties(title=f"Top 10 {column}", width="container")
            )

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                y=alt.Y(column, type="nominal"),
                x=alt.X("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip(column, type="nominal"),
                    alt.Tooltip(
                        "count()",
                        type="quantitative",
                        format=TOOLTIP_COUNT_FORMAT,
                    ),
                ],
            )
        )

    def altair_code(self, data: str, column: str) -> str:
        if self.should_limit_to_10_items:
            return f"""
            _chart = (
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
                .mark_bar()
                .encode(
                    y=alt.Y("{column}", type="nominal", sort="-x"),
                    x=alt.X("count", type="quantitative"),
                    tooltip=[
                        alt.Tooltip("{column}", type="nominal"),
                        alt.Tooltip(
                            "count",
                            type="quantitative",
                            format="{TOOLTIP_COUNT_FORMAT}",
                        ),
                    ],
                )
                .properties(title="Top 10 {column}", width="container")
            )
            _chart
            """

        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                y=alt.Y("{column}", type="nominal"),
                x=alt.X("count()", type="quantitative", format="{TOOLTIP_COUNT_FORMAT}"),
            )
            .properties(width="container")
        )
        _chart
        """


class DateChartBuilder(ChartBuilder):
    DEFAULT_DATE_FORMAT = "%Y-%m-%d"

    def _guess_date_format(self, data: Any, column: str) -> str:
        """Guess the appropriate date format based on the range of dates in the column."""
        if not can_narwhalify(data, eager_only=True):
            return "%Y-%m-%d"

        df = nw.from_native(data, eager_only=True)

        # Get min and max dates using narwhals
        min_date = df[column].min()
        max_date = df[column].max()

        # Calculate the difference in days
        time_diff = max_date - min_date
        if not hasattr(time_diff, "days"):
            return self.DEFAULT_DATE_FORMAT

        days_diff = time_diff.days

        # Choose format based on the range
        if days_diff > 365 * 10:  # More than 10 years
            return "%Y"  # Year only
        elif days_diff > 365:  # More than a year
            return "%Y-%m"  # Year and month
        elif days_diff > 31:  # More than a month
            return "%Y-%m-%d"  # Full date
        elif days_diff > 1:  # More than a day
            return "%Y-%m-%d %H"  # Date and time (hours)
        else:
            return "%Y-%m-%d %H:%M"  # Date and time (hours, minutes)

    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        date_format = self._guess_date_format(data, column)

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(
                    column,
                    type="temporal",
                    bin=alt.Bin(maxbins=20),
                    axis=alt.Axis(format=date_format),
                    title=column,
                ),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip(
                        column,
                        type="temporal",
                        bin=alt.Bin(maxbins=20),
                        format=date_format,
                        title=column,
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
        date_format = self._guess_date_format(data, column)
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X(
                    "{column}",
                    type="temporal",
                    bin=alt.Bin(maxbins=20),
                    axis=alt.Axis(format="{date_format}"),
                    title="{column}",
                ),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip(
                        "{column}",
                        type="temporal",
                        bin=alt.Bin(maxbins=20),
                        format="{date_format}",
                        title="{column}",
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


class BooleanChartBuilder(ChartBuilder):
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
                x=alt.X("{column}", type="nominal"),
                y=alt.Y("count()", type="quantitative"),
                tooltip=[
                    alt.Tooltip("{column}", type="nominal"),
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
