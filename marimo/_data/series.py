# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

DataFrameSeries = Union["pd.Series[Any]", "pl.Series"]


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


def _get_name(series: DataFrameSeries) -> str:
    return str(series.name) if series.name is not None else ""


def get_number_series_info(series: Any) -> NumberSeriesInfo:
    """
    Get the summary of a numeric series.
    """

    def validate_number(value: Any) -> float:
        value = float(value)
        if not isinstance(value, (int, float)):
            raise ValueError("Expected a number. Got: " + str(type(value)))
        return value

    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(series, pd.Series):
            return NumberSeriesInfo(
                min=validate_number(series.min()),
                max=validate_number(series.max()),
                label=_get_name(series),
            )

    if DependencyManager.has_polars():
        import polars as pl

        if isinstance(series, pl.Series):
            return NumberSeriesInfo(
                min=validate_number(series.min()),
                max=validate_number(series.max()),
                label=_get_name(series),
            )

    raise ValueError("Unsupported series type. Expected pandas or polars.")


def get_category_series_info(series: Any) -> CategorySeriesInfo:
    """
    Get the summary of a categorical series.
    """
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(series, pd.Series):
            return CategorySeriesInfo(
                categories=sorted(series.unique().tolist()),
                label=_get_name(series),
            )

    if DependencyManager.has_polars():
        import polars as pl

        if isinstance(series, pl.Series):
            return CategorySeriesInfo(
                categories=sorted(series.unique().to_list()),
                label=_get_name(series),
            )

    raise ValueError("Unsupported series type. Expected pandas or polars.")


def get_date_series_info(series: Any) -> DateSeriesInfo:
    """
    Get the summary of a date series.
    """

    def validate_date(value: Any) -> str:
        if not isinstance(value, datetime.date):
            raise ValueError("Expected a date. Got: " + str(type(value)))
        return value.strftime("%Y-%m-%d")

    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(series, pd.Series):
            return DateSeriesInfo(
                min=validate_date(series.min()),
                max=validate_date(series.max()),
                label=_get_name(series),
            )

    if DependencyManager.has_polars():
        import polars as pl

        if isinstance(series, pl.Series):
            return DateSeriesInfo(
                min=validate_date(series.min()),
                max=validate_date(series.max()),
                label=_get_name(series),
            )

    raise ValueError("Unsupported series type. Expected pandas or polars.")
