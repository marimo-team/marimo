# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, TypeVar, Union

from narwhals.typing import IntoDataFrame

from marimo import _loggers
from marimo._output.data import data as mo_data
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._types.ids import UIElementId

LOGGER = _loggers.marimo_logger()

DEFAULT_CSV_ENCODING = "utf-8"


def get_bound_name(element_id: UIElementId) -> str | None:
    """Get the bound variable name for a UI element.

    Looks up the element's bound names from the UI element registry
    at runtime. Returns the first (alphabetically sorted) bound name,
    or None if not found.

    Args:
        element_id: The unique ID of the UI element.

    Returns:
        The bound variable name, or None if not found.
    """
    try:
        ctx = get_context()
        bound = sorted(ctx.ui_element_registry.bound_names(element_id))
        return bound[0] if bound else None
    except ContextNotInitializedError:
        return None


def get_default_csv_encoding() -> str:
    """Get the default CSV encoding from config.

    Returns:
        str: The default CSV encoding, falling back to "utf-8" if not configured.
    """
    try:
        return (
            get_context()
            .marimo_config["runtime"]
            .get("default_csv_encoding", DEFAULT_CSV_ENCODING)
        )
    except ContextNotInitializedError:
        return DEFAULT_CSV_ENCODING


T = TypeVar("T")
Numeric = int | float
ListOrTuple = list[T] | tuple[T, ...]


# Use Union[] instead of X | Y — see altair_transformer.py for rationale.
TableData = Union[
    list[JSONType],
    ListOrTuple[Union[str, int, float, bool, MIME, None]],
    ListOrTuple[dict[str, JSONType]],
    dict[str, ListOrTuple[JSONType]],
    IntoDataFrame,
]


def download_as(
    manager: TableManager[Any],
    ext: str,
    drop_marimo_index: bool = False,
    csv_encoding: str | None = None,
    csv_separator: str | None = None,
    json_ensure_ascii: bool = True,
    filename: str | None = None,
) -> tuple[str, str]:
    """Download the table data in the specified format.

    Args:
        manager (TableManager[Any]): The table manager to download.
        ext (str): The format to download the table data in.
        drop_marimo_index (bool, optional): Whether to drop the marimo selection column.
            Defaults to False.
        csv_encoding (str | None, optional): Encoding used when generating CSV bytes.
            Defaults to the runtime config value (or "utf-8" if not configured).
            Ignored for non-CSV formats.
        csv_separator (str | None, optional): Separator used in CSV downloads.
            Defaults to "," when not configured.
        json_ensure_ascii (bool, optional): Whether to escape non-ASCII characters
            in JSON output. Defaults to True.
        filename (str | None, optional): The filename to use for the downloaded file.
            Defaults to None, which uses a random filename.

    Returns:
        tuple: (url, user-facing filename with extension) for the downloaded file.

    Raises:
        ValueError: If unrecognized format.
    """
    if drop_marimo_index:
        # Remove the selection column if exists
        manager = manager.drop_columns([INDEX_COLUMN_NAME])

    if ext == "csv":
        encoding = (
            csv_encoding
            if csv_encoding is not None
            else get_default_csv_encoding()
        )
        payload = manager.to_csv(encoding=encoding, separator=csv_separator)
        vfile = mo_data.csv(payload)
    elif ext == "json":
        # Use strict JSON to ensure compliance with JSON spec
        payload = manager.to_json(
            encoding=None, ensure_ascii=json_ensure_ascii, strict_json=True
        )
        vfile = mo_data.json(payload)
    elif ext == "parquet":
        payload = manager.to_parquet()
        vfile = mo_data.parquet(payload)
    else:
        raise ValueError("format must be one of 'csv', 'json', or 'parquet'.")

    base_name = filename if filename is not None else "download"
    return (vfile.url, f"{base_name}.{ext}")
