# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, cast

import narwhals.stable.v1 as nw

from marimo._utils.narwhals_utils import (
    assert_narwhals_series,
    unwrap_py_scalar,
)

# TODO: use series type when released
# https://github.com/narwhals-dev/narwhals/pull/991
DataFrameSeries = Any


@dataclass
class NumberSeriesInfo:
    """
    Represents a summary of a numeric series.
    """

    min: float
    max: float
    label: str


@dataclass
class CategorySeriesInfo:
    """
    Represents a summary of a categorical series.
    """

    categories: list[str]
    label: str


@dataclass
class DateSeriesInfo:
    """
    Represents a summary of a date series.
    """

    min: str
    max: str
    label: str


def _get_name(series: nw.Series) -> str:
    if series.name is None:
        return ""
    return str(series.name)


@nw.narwhalify(eager_or_interchange_only=True, series_only=True)
def get_number_series_info(series: nw.Series) -> NumberSeriesInfo:
    """
    Get the summary of a numeric series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()

    def validate_number(value: Any) -> float:
        value = unwrap_py_scalar(value)
        value = float(value)
        if not isinstance(value, (int, float)):
            raise ValueError("Expected a number. Got: " + str(type(value)))
        return value

    return NumberSeriesInfo(
        min=validate_number(series.min()),
        max=validate_number(series.max()),
        label=_get_name(series),
    )


@nw.narwhalify(eager_or_interchange_only=True, series_only=True)
def get_category_series_info(series: nw.Series) -> CategorySeriesInfo:
    """
    Get the summary of a categorical series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()

    return CategorySeriesInfo(
        categories=sorted(series.unique().to_list()),
        label=_get_name(series),
    )


@nw.narwhalify(eager_or_interchange_only=True, series_only=True)
def get_date_series_info(series: nw.Series) -> DateSeriesInfo:
    """
    Get the summary of a date series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()

    def validate_date(value: Any) -> str:
        value = unwrap_py_scalar(value)
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            return cast(str, value.strftime("%Y-%m-%d"))
        raise ValueError("Expected a date. Got: " + str(type(value)))

    return DateSeriesInfo(
        min=validate_date(series.min()),
        max=validate_date(series.max()),
        label=_get_name(series),
    )


@nw.narwhalify(eager_or_interchange_only=True, series_only=True)
def get_datetime_series_info(series: nw.Series) -> DateSeriesInfo:
    """
    Get the summary of a datetime series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()

    def validate_datetime(value: Any) -> str:
        value = unwrap_py_scalar(value)
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(value, datetime.date):
            # Convert date to datetime
            value = datetime.datetime(value.year, value.month, value.day)
            return value.strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            return cast(str, value.strftime("%Y-%m-%d"))
        raise ValueError("Expected a datetime. Got: " + str(type(value)))

    return DateSeriesInfo(
        min=validate_datetime(series.min()),
        max=validate_datetime(series.max()),
        label=_get_name(series),
    )
