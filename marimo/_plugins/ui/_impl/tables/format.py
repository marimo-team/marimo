# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Dict, List, Union

from marimo._plugins.ui._impl.tables.table_manager import JSONType

FormatMapping = Dict[str, Union[str, Callable[..., Any]]]


def format_value(
    col: str, value: JSONType, format_mapping: FormatMapping
) -> JSONType:
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
    # Apply formatting to each value in a row dictionary
    return {
        col: format_value(col, value, format_mapping)
        for col, value in row.items()
    }


def format_column(
    col: str, values: List[JSONType], format_mapping: FormatMapping
) -> List[JSONType]:
    # Apply formatting to each value in a column list
    return [format_value(col, value, format_mapping) for value in values]
