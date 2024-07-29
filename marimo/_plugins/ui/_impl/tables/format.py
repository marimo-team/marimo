# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Dict, List, Union

from marimo._plugins.core.web_component import JSONType

FormatMapping = Dict[str, Union[str, Callable[..., JSONType]]]


def format_value(
    col: str, value: JSONType, format_mapping: FormatMapping
) -> JSONType:
    # Return None if the format mapping is None
    if format_mapping is None:
        return value
    # Return None if the value is None
    if value is None:
        return None
    # Apply formatting logic based on column and value
    if col in format_mapping:
        formatter = format_mapping[col]
        if isinstance(formatter, str):
            return formatter.format(value)
        if callable(formatter):
            return formatter(value)
    return value


def format_row(
    row: Dict[str, JSONType], format_mapping: FormatMapping
) -> Dict[str, JSONType]:
    # Return None if the format mapping is None
    if format_mapping is None:
        return row
    # Apply formatting to each value in a row dictionary
    return {
        col: format_value(col, value, format_mapping)
        for col, value in row.items()
    }


def format_column(
    col: str, values: List[JSONType], format_mapping: FormatMapping
) -> List[JSONType]:
    # Return None if the format mapping is None
    if format_mapping is None:
        return values
    # Apply formatting to each value in a column list
    return [format_value(col, value, format_mapping) for value in values]
