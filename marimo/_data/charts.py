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
        import altair as alt

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="quantitative", bin=True),
                y=alt.Y("count()", type="quantitative"),
            )
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
        )
        _chart
        """


class StringChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

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
            .transform_calculate(
                **{
                    column: alt.expr.if_(
                        alt.datum.rank <= 10,
                        alt.datum[column],
                        "Other",
                    )
                },
            )
            .transform_filter(alt.datum.rank <= 11)
            .mark_bar()
            .encode(
                y=alt.Y(column, type="nominal", sort="-x"),
                x=alt.X("count", type="quantitative"),
            )
        )

    def altair_code(self, data: str, column: str) -> str:
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
            .transform_calculate(
                {column}=alt.expr.if_(
                    alt.datum.rank <= 10,
                    alt.datum["{column}"],
                    "Other",
                ),
            )
            .transform_filter(alt.datum.rank <= 11)
            .mark_bar()
            .encode(
                y=alt.Y("{column}", type="nominal", sort="-x"),
                x=alt.X("count", type="quantitative"),
            )
        )
        _chart
        """


class DateChartBuilder(ChartBuilder):
    def altair(self, data: Any, column: str) -> Any:
        import altair as alt

        return (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(column, type="temporal"),
                y=alt.Y("count()", type="quantitative"),
            )
        )

    def altair_code(self, data: str, column: str) -> str:
        return f"""
        _chart = (
            alt.Chart({data})
            .mark_bar()
            .encode(
                x=alt.X("{column}", type="temporal"),
                y=alt.Y("count()", type="quantitative"),
            )
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
            )
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
                x=alt.X(column, type="quantitative", bin=True),
                y=alt.Y("count()", type="quantitative"),
            )
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
            )
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
        )
        _chart
        """


class WrapperChartBuilder(ChartBuilder):
    def __init__(self, delegate: ChartBuilder):
        self.delegate = delegate

    def altair(self, data: Any, column: str) -> Any:
        return self.delegate.altair_json(data, column)

    def altair_code(self, data: str, column: str) -> str:
        return dedent(self.delegate.altair_code(data, column)).strip()


def get_chart_builder(column_type: DataType) -> ChartBuilder:
    if column_type == "number":
        return WrapperChartBuilder(NumberChartBuilder())
    if column_type == "string":
        return WrapperChartBuilder(StringChartBuilder())
    if column_type == "date":
        return WrapperChartBuilder(DateChartBuilder())
    if column_type == "boolean":
        return WrapperChartBuilder(BooleanChartBuilder())
    if column_type == "integer":
        return WrapperChartBuilder(IntegerChartBuilder())
    if column_type == "unknown":
        return WrapperChartBuilder(UnknownChartBuilder())
