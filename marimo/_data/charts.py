# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, cast

from marimo._data.models import DataType


@abc.abstractmethod
class ChartBuilder:
    @abc.abstractmethod
    def altair(self, data: Any, column: str) -> Any:
        raise NotImplementedError

    def altair_json(self, data: Any, column: str) -> str:
        return cast(str, self.altair(data, column).to_json())

    @abc.abstractmethod
    def altair_code(self, data: str, column: str) -> str:
        raise NotImplementedError


@dataclass
class ChartParams:
    table_name: str
    column: str


class NumberChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="quantitative", bin=True),
                y=alt.Y("count()", type="quantitative"),
            )
            .properties(width="container")
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="quantitative", bin=True),
                y=alt.Y("count()", type="quantitative"),
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
        import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

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
                )
                .properties(title=f"Top 10 {column}", width="container")
            )

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                y=alt.Y(column, type="nominal"),
                x=alt.X("count()", type="quantitative"),
            )
            .properties(width="container")
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
                x=alt.X("count()", type="quantitative"),
            )
            .properties(width="container")
        )
        _chart
        """


class DateChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        return (
            alt.Chart(data)
            .mark_line(point={"filled": False, "fill": "white"})
            .encode(
                x=alt.X(column, type="temporal"),
                y=alt.Y("count()", type="quantitative"),
            )
            .properties(width="container")
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_line(point={{"filled": False, "fill": "white"}})
            .encode(
                x=alt.X("{column}", type="temporal"),
                y=alt.Y("count()", type="quantitative"),
            )
            .properties(width="container")
        )
        _chart
        """


class BooleanChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="nominal"),
                y=alt.Y("count()", type="quantitative"),
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
            )
            .properties(width="container")
        )
        _chart
        """


class IntegerChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="quantitative", bin=True),
                y=alt.Y("count()", type="quantitative"),
            )
            .properties(width="container")
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="quantitative", bin=True),
                y=alt.Y("count()", type="quantitative"),
            )
            .properties(width="container")
        )
        _chart
        """


class UnknownChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="nominal"),
                y=alt.Y("count()", type="quantitative"),
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
    if column_type == "date":
        return WrapperChartBuilder(DateChartBuilder())
    if column_type == "boolean":
        return WrapperChartBuilder(BooleanChartBuilder())
    if column_type == "integer":
        return WrapperChartBuilder(IntegerChartBuilder())
    if column_type == "unknown":
        return WrapperChartBuilder(UnknownChartBuilder())


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
