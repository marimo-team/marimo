# Copyright 2026 Marimo. All rights reserved.
"""Decode fetched DuckDB file bytes into pandas DataFrames.

The WASM patch fetches remote bytes in Python, but DuckDB's Python readers
still expect local paths for CSV, JSON, and parquet parsing. This module
materializes fetched bytes through short-lived temp files where DuckDB parsing
is needed and synthesizes DataFrames for ``read_text`` and ``read_blob``.
"""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import pandas as pd

_CSV_SUFFIXES = (".csv.gz", ".tsv.gz", ".csv", ".tsv")
_JSON_SUFFIXES = (
    ".geojson.gz",
    ".ndjson.gz",
    ".jsonl.gz",
    ".json.gz",
    ".geojson",
    ".ndjson",
    ".jsonl",
    ".json",
)
_JSON_OBJECT_FUNCTIONS = frozenset(
    {
        "read_json_objects",
        "read_json_objects_auto",
        "read_ndjson_objects",
    }
)


def read_csv_dataframe(
    data: bytes, options: Mapping[str, Any], *, url: str
) -> pd.DataFrame:
    """Read CSV/TSV bytes with a suffix that preserves compression hints."""
    import duckdb

    return _read_temp_dataframe(
        data,
        suffix=_temp_suffix(
            url,
            suffixes=_CSV_SUFFIXES,
            default=".csv",
        ),
        reader=lambda path: duckdb.from_csv_auto(path, **options).df(),
    )


def read_parquet_dataframe(data: bytes) -> pd.DataFrame:
    import duckdb

    return _read_temp_dataframe(
        data,
        suffix=".parquet",
        reader=lambda path: duckdb.read_parquet(path).df(),
    )


def read_json_dataframe(
    data: bytes, options: Mapping[str, Any], *, url: str
) -> pd.DataFrame:
    import duckdb

    return _read_temp_dataframe(
        data,
        suffix=_temp_suffix(
            url,
            suffixes=_JSON_SUFFIXES,
            default=".json",
        ),
        reader=lambda path: duckdb.read_json(path, **options).df(),
    )


def read_json_objects_dataframe(
    data: bytes, options: Mapping[str, Any], *, url: str, function_name: str
) -> pd.DataFrame:
    """Read JSON-object bytes through DuckDB's SQL-only table function."""
    if function_name not in _JSON_OBJECT_FUNCTIONS:
        raise ValueError(
            f"Unsupported DuckDB JSON object reader: {function_name}"
        )

    return _read_temp_dataframe(
        data,
        suffix=_temp_suffix(
            url,
            suffixes=_JSON_SUFFIXES,
            default=".json",
        ),
        reader=lambda path: _read_json_objects_path(
            path, options, function_name
        ),
    )


def _read_json_objects_path(
    path: str, options: Mapping[str, Any], function_name: str
) -> pd.DataFrame:
    import duckdb

    # DuckDB exposes JSON-object readers as SQL table functions, not Python
    # module methods, so invoke the table function with bound parameters.
    option_items = tuple(options.items())
    query_args = ["?"]
    query_args.extend(f"{key} := ?" for key, _ in option_items)
    return duckdb.sql(
        f"SELECT * FROM {function_name}({', '.join(query_args)})",
        params=[path, *(value for _, value in option_items)],
    ).df()


def read_text_dataframe(data: bytes, url: str) -> pd.DataFrame:
    """Match DuckDB's ``read_text`` shape for an already-fetched object."""
    import pandas as pd

    return pd.DataFrame(
        {
            "filename": [url],
            "content": [data.decode("utf-8")],
            "size": [len(data)],
            "last_modified": [pd.NaT],
        }
    )


def read_blob_dataframe(data: bytes, url: str) -> pd.DataFrame:
    """Match DuckDB's ``read_blob`` shape for an already-fetched object."""
    import pandas as pd

    return pd.DataFrame(
        {
            "filename": [url],
            "content": [data],
            "size": [len(data)],
            "last_modified": [pd.NaT],
        }
    )


def append_filename_column(
    df: pd.DataFrame, url: str, column_name: str
) -> pd.DataFrame:
    """Apply DuckDB's filename option after bytes have been decoded."""
    if column_name in df.columns:
        raise ValueError(
            f'Option filename adds column "{column_name}", but a column with this '
            "name is also in the file"
        )

    df = df.copy()
    df[column_name] = url
    return df


def _read_temp_dataframe(
    data: bytes,
    *,
    suffix: str,
    reader: Callable[[str], pd.DataFrame],
) -> pd.DataFrame:
    """Materialize fetched bytes so DuckDB can parse them from a local path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        return reader(path)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def _temp_suffix(url: str, *, suffixes: tuple[str, ...], default: str) -> str:
    """Preserve file extensions so DuckDB can infer format details."""
    path = urlparse(url).path.lower()
    for suffix in suffixes:
        if path.endswith(suffix):
            return suffix
    return default
