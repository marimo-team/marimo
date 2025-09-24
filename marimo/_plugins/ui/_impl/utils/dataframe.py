# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, TypeVar, Union

from narwhals.typing import IntoDataFrame

from marimo import _loggers
from marimo._output.data import data as mo_data
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import TableManager

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")
Numeric = Union[int, float]
ListOrTuple = Union[list[T], tuple[T, ...]]


TableData = Union[
    list[JSONType],
    ListOrTuple[Union[str, int, float, bool, MIME, None]],
    ListOrTuple[dict[str, JSONType]],
    dict[str, ListOrTuple[JSONType]],
    IntoDataFrame,
]


def download_as(
    manager: TableManager[Any], ext: str, drop_marimo_index: bool = False
) -> str:
    """Download the table data in the specified format.

    Args:
        manager (TableManager[Any]): The table manager to download.
        ext (str): The format to download the table data in.
        drop_marimo_index (bool, optional): Whether to drop the marimo selection column.
            Defaults to False.

    Raises:
        ValueError: If unrecognized format.
        NotImplementedError: If the table format is not supported.

    Returns:
        str: The URL to download the table data.
    """
    if drop_marimo_index:
        # Remove the selection column if exists
        manager = manager.drop_columns([INDEX_COLUMN_NAME])

    if ext == "csv":
        return mo_data.csv(manager.to_csv()).url
    elif ext == "json":
        return mo_data.json(manager.to_json()).url
    elif ext == "parquet":
        return mo_data.parquet(manager.to_parquet()).url
    else:
        raise ValueError("format must be one of 'csv', 'json', or 'parquet'.")
