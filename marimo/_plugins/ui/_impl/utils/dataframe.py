# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar, Union

from narwhals.typing import IntoDataFrame, IntoLazyFrame

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

if TYPE_CHECKING:
    from collections.abc import Callable

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
    list[dict[str, Any]],
    dict[str, list[Any]],
    dict[str, ListOrTuple[JSONType]],
    IntoDataFrame,
    IntoLazyFrame,
]


@dataclass(frozen=True)
class DelimitedOptions:
    """Output options shared by delimited-text formats (CSV, TSV).

    Attributes:
        encoding: Text encoding for the output bytes. Falls back to the
            runtime config value (or "utf-8") when None.
        separator: Field separator. Ignored by formats that pin their own
            separator (e.g. TSV always uses a tab).
    """

    encoding: str | None = None
    separator: str | None = None


@dataclass(frozen=True)
class JsonOptions:
    """Output options for the JSON format.

    Attributes:
        ensure_ascii: Whether to escape non-ASCII characters.
    """

    ensure_ascii: bool = True


@dataclass(frozen=True)
class DownloadOptions:
    """Per-format output options for `download_as`."""

    delimited: DelimitedOptions = field(default_factory=DelimitedOptions)
    json: JsonOptions = field(default_factory=JsonOptions)


@dataclass(frozen=True)
class _ExportFormat:
    extension: str
    serialize: Callable[[TableManager[Any], DownloadOptions], bytes]


def _serialize_delimited(
    separator_override: str | None,
) -> Callable[[TableManager[Any], DownloadOptions], bytes]:
    def serialize(
        manager: TableManager[Any], options: DownloadOptions
    ) -> bytes:
        encoding = options.delimited.encoding or get_default_csv_encoding()
        separator = (
            separator_override
            if separator_override is not None
            else options.delimited.separator
        )
        return manager.to_csv(encoding=encoding, separator=separator)

    return serialize


def _serialize_json(
    manager: TableManager[Any], options: DownloadOptions
) -> bytes:
    # Use strict JSON to ensure compliance with JSON spec
    return manager.to_json(
        encoding=None,
        ensure_ascii=options.json.ensure_ascii,
        strict_json=True,
    )


def _serialize_parquet(
    manager: TableManager[Any], _options: DownloadOptions
) -> bytes:
    return manager.to_parquet()


_EXPORT_FORMATS: dict[str, _ExportFormat] = {
    "csv": _ExportFormat("csv", _serialize_delimited(None)),
    "tsv": _ExportFormat("tsv", _serialize_delimited("\t")),
    "json": _ExportFormat("json", _serialize_json),
    "parquet": _ExportFormat("parquet", _serialize_parquet),
}


def download_as(
    manager: TableManager[Any],
    ext: str,
    drop_marimo_index: bool = False,
    options: DownloadOptions | None = None,
    filename: str | None = None,
) -> tuple[str, str]:
    """Download the table data in the specified format.

    Args:
        manager (TableManager[Any]): The table manager to download.
        ext (str): The format to download the table data in. One of
            `csv`, `tsv`, `json`, or `parquet`.
        drop_marimo_index (bool, optional): Whether to drop the marimo
            selection column. Defaults to False.
        options (DownloadOptions | None, optional): Per-format output
            options (delimited encoding/separator, JSON ascii escaping).
            Defaults to each format's defaults.
        filename (str | None, optional): The filename to use for the
            downloaded file. Defaults to None, which uses a random filename.

    Returns:
        tuple: (url, user-facing filename with extension) for the downloaded file.

    Raises:
        ValueError: If unrecognized format.
    """
    options = options or DownloadOptions()
    if drop_marimo_index:
        # Remove the selection column if exists
        manager = manager.drop_columns([INDEX_COLUMN_NAME])

    fmt = _EXPORT_FORMATS.get(ext)
    if fmt is None:
        allowed = ", ".join(map(repr, _EXPORT_FORMATS))
        raise ValueError(f"format must be one of {allowed}.")

    vfile = mo_data.any_data(
        fmt.serialize(manager, options), ext=fmt.extension
    )
    base_name = filename if filename is not None else "download"
    return (vfile.url, f"{base_name}.{fmt.extension}")
