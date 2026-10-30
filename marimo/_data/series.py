# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
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

    min: float | None
    max: float | None
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

    min: str | None
    max: str | None
    label: str


def _get_name(series: nw.Series[Any]) -> str:
    if series.name is None:
        return ""
    return str(series.name)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(value != value)  # noqa: PLR0124
    except (TypeError, ValueError):
        return False


@nw.narwhalify(eager_only=True, series_only=True)
def get_number_series_info(series: nw.Series[Any]) -> NumberSeriesInfo:
    """
    Get the summary of a numeric series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()
    raw_min = series.min()
    raw_max = series.max()

    def validate_number(value: Any) -> float:
        value = unwrap_py_scalar(value)
        if _is_missing(value):
            raise ValueError("Series has no non-null numeric values")
        value = float(value)
        if not isinstance(value, (int, float)):
            raise ValueError("Expected a number. Got: " + str(type(value)))
        return value

    return NumberSeriesInfo(
        min=(
            None
            if series.len() == 0 or _is_missing(raw_min)
            else validate_number(raw_min)
        ),
        max=(
            None
            if series.len() == 0 or _is_missing(raw_max)
            else validate_number(raw_max)
        ),
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
    raw_min = series.min()
    raw_max = series.max()
    raw_min = series.min()
    raw_max = series.max()

    def validate_date(value: Any) -> str:
        value = unwrap_py_scalar(value)
        if _is_missing(value):
            raise ValueError("Series has no non-null date values")
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            return cast(str, value.strftime("%Y-%m-%d"))
        raise ValueError("Expected a date. Got: " + str(type(value)))

    return DateSeriesInfo(
        min=(
            None
            if series.len() == 0 or _is_missing(raw_min)
            else validate_date(raw_min)
        ),
        max=(
            None
            if series.len() == 0 or _is_missing(raw_max)
            else validate_date(raw_max)
        ),
        label=_get_name(series),
    )


@nw.narwhalify(eager_only=True, series_only=True)
def get_datetime_series_info(series: nw.Series[Any]) -> DateSeriesInfo:
    """
    Get the summary of a datetime series.
    """
    assert_narwhals_series(series)

    series = series.drop_nulls()
    raw_min = series.min()
    raw_max = series.max()

    def validate_datetime(value: Any) -> str:
        value = unwrap_py_scalar(value)
        if _is_missing(value):
            raise ValueError("Series has no non-null datetime values")
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
        min=(
            None
            if series.len() == 0 or _is_missing(raw_min)
            else validate_datetime(raw_min)
        ),
        max=(
            None
            if series.len() == 0 or _is_missing(raw_max)
            else validate_datetime(raw_max)
        ),
        label=_get_name(series),
    )
