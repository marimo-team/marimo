# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from typing import Any, cast

import narwhals.stable.v2 as nw
from narwhals.typing import IntoSeries

from marimo._utils.narwhals_utils import (
    assert_narwhals_series,
    unwrap_py_scalar,
)

DataFrameSeries = IntoSeries


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


def _get_name(series: nw.Series[Any]) -> str:
    if series.name is None:
        return ""
    return str(series.name)


@nw.narwhalify(eager_only=True, series_only=True)
def get_series_name(series: nw.Series[Any]) -> str:
    """
    Get the name of a series.
    """
    assert_narwhals_series(series)
    return _get_name(series)


@nw.narwhalify(eager_only=True, series_only=True)
def get_number_series_info(series: nw.Series[Any]) -> NumberSeriesInfo:
    """
    Get the summary of a numeric series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()
    if series.is_empty():
        raise ValueError(
            "Cannot get series info: series is empty or contains only null values."
        )

    def validate_number(value: Any) -> float:
        value = unwrap_py_scalar(value)
        if value is None or isinstance(value, bool):
            raise ValueError(f"Expected a number. Got: {type(value)}")
        try:
            num = float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Expected a number. Got: {type(value)}") from e
        if math.isnan(num):
            raise ValueError("Expected a number. Got: NaN")
        return num

    return NumberSeriesInfo(
        min=validate_number(series.min()),
        max=validate_number(series.max()),
        label=_get_name(series),
    )


@nw.narwhalify(eager_only=True, series_only=True)
def get_category_series_info(series: nw.Series[Any]) -> CategorySeriesInfo:
    """
    Get the summary of a categorical series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()

    return CategorySeriesInfo(
        categories=sorted(series.unique().to_list()),
        label=_get_name(series),
    )


@nw.narwhalify(eager_only=True, series_only=True)
def get_date_series_info(series: nw.Series[Any]) -> DateSeriesInfo:
    """
    Get the summary of a date series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()
    if series.is_empty():
        raise ValueError(
            "Cannot get series info: series is empty or contains only null values."
        )

    def validate_date(value: Any) -> str:
        value = unwrap_py_scalar(value)
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            try:
                return cast(str, value.strftime("%Y-%m-%d"))
            except (ValueError, TypeError) as e:
                raise ValueError(
                    "Expected a date. Got: " + str(type(value))
                ) from e
        raise ValueError("Expected a date. Got: " + str(type(value)))

    return DateSeriesInfo(
        min=validate_date(series.min()),
        max=validate_date(series.max()),
        label=_get_name(series),
    )


@nw.narwhalify(eager_only=True, series_only=True)
def get_datetime_series_info(series: nw.Series[Any]) -> DateSeriesInfo:
    """
    Get the summary of a datetime series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()
    if series.is_empty():
        raise ValueError(
            "Cannot get series info: series is empty or contains only null values."
        )

    def validate_datetime(value: Any) -> str:
        value = unwrap_py_scalar(value)
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(value, datetime.date):
            # Convert date to datetime
            value = datetime.datetime(value.year, value.month, value.day)
            return value.strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            try:
                return cast(str, value.strftime("%Y-%m-%d"))
            except (ValueError, TypeError) as e:
                raise ValueError(
                    "Expected a datetime. Got: " + str(type(value))
                ) from e
        raise ValueError("Expected a datetime. Got: " + str(type(value)))

    return DateSeriesInfo(
        min=validate_datetime(series.min()),
        max=validate_datetime(series.max()),
        label=_get_name(series),
    )
