# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import warnings
from typing import Any

from marimo._dependencies.dependencies import DependencyManager


def validate_range(
    min_value: int | float | None,
    max_value: int | float | None,
) -> None:
    if min_value is not None:
        validate_number(min_value)
    if max_value is not None:
        validate_number(max_value)
    if (
        min_value is not None
        and max_value is not None
        and min_value > max_value
    ):
        raise ValueError("min/start must be less than or equal to max/end")


def validate_between_range(
    value: int | float | None,
    min_value: int | float | None,
    max_value: int | float | None,
) -> None:
    if value is None:
        return

    validate_number(value)
    if min_value is not None and value < min_value:
        raise ValueError(f"Value must be greater than or equal to {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"Value must be less than or equal to {max_value}")


def validate_number(
    value: Any,
) -> None:
    if not isinstance(value, (int, float)):
        raise TypeError("Value must be a number")


def warn_js_safe_number(*values: int | float | None) -> None:
    # Number.MAX_SAFE_INTEGER in JavaScript
    MAX_SAFE_INTEGER = 9007199254740991

    for value in values:
        # Skip None values
        if not isinstance(value, (int, float)):
            continue
        if abs(value) > MAX_SAFE_INTEGER:
            warnings.warn(
                f"Warning: Value {value} is outside the range of safe "
                "integers in JavaScript. This may cause precision issues.",
                stacklevel=3,
            )


def validate_no_integer_columns(df: Any) -> None:
    if not DependencyManager.pandas.imported():
        return

    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        return

    has_int_column_names = any(isinstance(name, int) for name in df.columns)
    if has_int_column_names:
        warnings.warn(
            "DataFrame has integer column names. This is not supported and can lead to bugs. "
            "Please use strings for column names.",
            stacklevel=3,
        )


# issue: https://github.com/marimo-team/marimo/issues/3407
def validate_page_size(page_size: int) -> None:
    if page_size > 200:
        raise ValueError(
            "Page size limited to 200 rows. If you'd like this increased, please file an issue"
        )
