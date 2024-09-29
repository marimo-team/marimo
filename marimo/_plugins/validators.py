# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import warnings
from typing import Any


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
