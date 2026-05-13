# Copyright 2026 Marimo. All rights reserved.
"""Resolve DuckDB remote file reads into fetch and DataFrame reader steps.

DuckDB's native network scanner is unavailable in Pyodide. This module is the
compatibility layer that recognizes supported URL shapes, validates the reader
options we can reproduce, fetches bytes through WASM fetch shim, and
dispatches to a local DataFrame reader. Unsupported readers or option
combinations return ``None`` so callers can use the unpatched DuckDB path
and surface the underlying error.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlparse

from marimo._runtime._wasm import _fetch
from marimo._runtime._wasm._duckdb.dataframe import (
    append_filename_column,
    read_blob_dataframe,
    read_csv_dataframe,
    read_json_dataframe,
    read_json_objects_dataframe,
    read_parquet_dataframe,
    read_text_dataframe,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pandas as pd


_ReaderName = str


@dataclass(frozen=True)
class _FetchedBytes:
    url: str
    data: bytes


@dataclass(frozen=True)
class RemoteFile:
    url: str

    def fetch(self) -> _FetchedBytes:
        """Fetch through the browser-backed Pyodide HTTP shim."""
        return _FetchedBytes(
            url=self.url,
            data=_fetch.fetch_url_bytes(self.url),
        )


@dataclass(frozen=True)
class _ReadRequest:
    file: _FetchedBytes
    function_name: str
    options: Mapping[str, Any]


class _DataFrameReader(Protocol):
    name: str
    direct_extensions: tuple[str, ...]
    function_names: tuple[str, ...]

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None: ...

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame: ...


class _CsvReader:
    name = "csv"
    direct_extensions: tuple[str, ...] = (
        ".csv",
        ".csv.gz",
        ".tsv",
        ".tsv.gz",
    )
    function_names: tuple[str, ...] = ("read_csv", "read_csv_auto")

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        del function_name
        options: dict[str, Any] = {}
        for key, value in raw_options.items():
            if key in {"delim", "delimiter", "sep", "separator"}:
                options["delimiter"] = _normalize_delimiter(value)
            elif key == "header":
                options["header"] = value
            elif key in {"auto_detect", "normalize_names"}:
                options[key] = value
            elif _apply_shared_source_option(options, key, value):
                pass
            else:
                return None
        return options

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame:
        return read_csv_dataframe(
            request.file.data,
            _csv_reader_options(request.options),
            url=request.file.url,
        )


class _ParquetReader:
    name = "parquet"
    direct_extensions: tuple[str, ...] = (".parquet", ".parq")
    function_names: tuple[str, ...] = ("read_parquet", "parquet_scan")

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        del function_name
        options: dict[str, Any] = {}
        for key, value in raw_options.items():
            if _apply_common_table_option(options, key, value):
                pass
            else:
                return None
        return options

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame:
        return read_parquet_dataframe(request.file.data)


class _JsonReader:
    name = "json"
    direct_extensions: tuple[str, ...] = (
        ".json",
        ".json.gz",
        ".geojson",
        ".geojson.gz",
        ".jsonl",
        ".jsonl.gz",
        ".ndjson",
        ".ndjson.gz",
    )
    function_names: tuple[str, ...] = (
        "read_json",
        "read_json_auto",
        "read_ndjson",
    )

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        options: dict[str, Any] = {}
        if function_name == "read_ndjson":
            options["format"] = "newline_delimited"

        for key, value in raw_options.items():
            if not _apply_json_option(options, key, value):
                return None
        return options

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame:
        return read_json_dataframe(
            request.file.data,
            _json_reader_options(request.options),
            url=request.file.url,
        )


class _JsonObjectsReader:
    name = "json_objects"
    direct_extensions: tuple[str, ...] = ()
    function_names: tuple[str, ...] = (
        "read_json_objects",
        "read_json_objects_auto",
        "read_ndjson_objects",
    )

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        options: dict[str, Any] = {}
        if function_name == "read_ndjson_objects":
            options["format"] = "newline_delimited"

        for key, value in raw_options.items():
            if not _apply_json_option(options, key, value):
                return None
        return options

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame:
        return read_json_objects_dataframe(
            request.file.data,
            _json_reader_options(request.options),
            url=request.file.url,
            function_name=request.function_name,
        )


class _TextReader:
    name = "text"
    direct_extensions: tuple[str, ...] = ()
    function_names: tuple[str, ...] = ("read_text",)

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        del function_name
        return {} if not raw_options else None

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame:
        return read_text_dataframe(request.file.data, request.file.url)


class _BlobReader:
    name = "blob"
    direct_extensions: tuple[str, ...] = ()
    function_names: tuple[str, ...] = ("read_blob",)

    def read_options(
        self,
        function_name: str,
        raw_options: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        del function_name
        return {} if not raw_options else None

    def read_dataframe(self, request: _ReadRequest) -> pd.DataFrame:
        return read_blob_dataframe(request.file.data, request.file.url)


_READERS: tuple[_DataFrameReader, ...] = (
    _CsvReader(),
    _ParquetReader(),
    _JsonReader(),
    _JsonObjectsReader(),
    _TextReader(),
    _BlobReader(),
)


@dataclass(frozen=True)
class RemoteFileSource:
    files: tuple[RemoteFile, ...]
    reader_name: _ReaderName
    options: tuple[tuple[str, Any], ...] = ()
    function_name: str | None = None

    def read_options(self) -> dict[str, Any]:
        """Expose sorted, hashable options as regular reader kwargs."""
        return dict(self.options)

    def read_dataframe(self) -> pd.DataFrame:
        """Read one or more remote files using DuckDB-compatible concat rules."""
        frames = [self._read_file_dataframe(file) for file in self.files]
        if len(frames) == 1:
            return frames[0]

        import pandas as pd

        if self.read_options().get("union_by_name") is True:
            return pd.concat(frames, ignore_index=True, sort=False)

        columns = list(frames[0].columns)
        for frame in frames[1:]:
            if list(frame.columns) != columns:
                raise ValueError(
                    "DuckDB WASM remote sources must have matching columns "
                    "unless union_by_name=True"
                )
        return pd.concat(frames, ignore_index=True)

    def _read_file_dataframe(self, file: RemoteFile) -> pd.DataFrame:
        """Fetch bytes, decode them, then apply DuckDB's filename option."""
        fetched = file.fetch()
        options = self.read_options()
        reader = _reader_by_name(self.reader_name)
        df = reader.read_dataframe(
            _ReadRequest(
                file=fetched,
                function_name=self.function_name or reader.function_names[0],
                options=options,
            )
        )
        filename = options.get("filename")
        if filename is True:
            return append_filename_column(df, fetched.url, "filename")
        if isinstance(filename, str):
            return append_filename_column(df, fetched.url, filename)
        return df


def remote_file_from_url(url: str) -> RemoteFile | None:
    """Return a fetchable remote file only for URL schemes marimo supports."""
    if urlparse(url).scheme not in {"http", "https"}:
        return None
    return RemoteFile(url=url)


def remote_file_source_from_reader_args(
    function_name: str,
    source: Any,
    raw_options: Mapping[str, Any],
) -> RemoteFileSource | None:
    """Map a DuckDB reader call to a reproducible remote DataFrame source."""
    reader = reader_for_function(function_name)
    if reader is None:
        return None

    files = _remote_files_from_source_arg(source)
    if files is None:
        return None

    options = reader.read_options(function_name, raw_options)
    if options is None:
        return None
    return RemoteFileSource(
        files,
        reader.name,
        tuple(sorted(options.items())),
        function_name=function_name,
    )


def _remote_files_from_source_arg(
    source: Any,
) -> tuple[RemoteFile, ...] | None:
    """Accept DuckDB source shapes that are static URL strings or URL lists."""
    if isinstance(source, str):
        file = remote_file_from_url(source)
        return (file,) if file is not None else None

    if isinstance(source, Sequence) and not isinstance(
        source, bytes | bytearray
    ):
        files: list[RemoteFile] = []
        for item in source:
            if not isinstance(item, str):
                return None
            file = remote_file_from_url(item)
            if file is None:
                return None
            files.append(file)
        return tuple(files) if files else None

    return None


def _reader_by_name(
    name: _ReaderName,
) -> _DataFrameReader:
    for reader in _READERS:
        if reader.name == name:
            return reader
    raise KeyError(f"Unknown DuckDB WASM reader: {name}")


def reader_for_url(url: str) -> _DataFrameReader | None:
    """Infer a reader from direct URL table syntax such as ``FROM 'x.csv'``."""
    path = urlparse(url).path.lower()
    return next(
        (
            reader
            for reader in _READERS
            if path.endswith(reader.direct_extensions)
        ),
        None,
    )


def reader_for_function(
    function_name: str,
) -> _DataFrameReader | None:
    """Resolve DuckDB table-function names to marimo's fallback readers."""
    return next(
        (
            reader
            for reader in _READERS
            if function_name in reader.function_names
        ),
        None,
    )


def _csv_reader_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Drop options implemented outside DuckDB's CSV reader call."""
    return {
        key: value
        for key, value in options.items()
        if key not in {"filename", "union_by_name"}
    }


def _json_reader_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Translate DuckDB JSON option spelling to DuckDB Python API spelling."""
    return {
        key: _normalize_json_reader_option(key, value)
        for key, value in options.items()
        if key not in {"filename", "union_by_name"}
    }


def _normalize_delimiter(value: Any) -> Any:
    """Convert SQL's escaped tab literal to the byte delimiter DuckDB expects."""
    if value == r"\t":
        return "\t"
    return value


def _normalize_json_reader_option(key: str, value: Any) -> Any:
    """Normalize JSON values whose SQL names differ from Python reader values."""
    if key == "compression":
        return _normalize_json_compression(value)
    if key == "format":
        return _normalize_json_format(value)
    return value


def _normalize_json_compression(value: Any) -> str:
    """Map SQL compression aliases to DuckDB Python JSON reader values."""
    compression = str(value).lower()
    if compression == "auto":
        return "auto_detect"
    if compression == "none":
        return "uncompressed"
    return compression


def _normalize_json_format(value: Any) -> str:
    """Map DuckDB SQL JSON format aliases to Python reader values."""
    fmt = str(value).lower()
    if fmt == "ndjson":
        return "newline_delimited"
    if fmt == "array_of_objects":
        return "array"
    return fmt


def _apply_json_option(options: dict[str, Any], key: str, value: Any) -> bool:
    """Keep JSON options only when the fallback can safely pass them through."""
    if key == "format":
        options["format"] = _normalize_json_format(value)
        return True
    if _apply_shared_source_option(options, key, value):
        return True
    if _is_safe_reader_option_name(key):
        options[key] = value
        return True
    return False


def _is_safe_reader_option_name(key: str) -> bool:
    """Reject option names that cannot be passed as Python reader kwargs."""
    return key.isidentifier()


def _apply_common_table_option(
    options: dict[str, Any], key: str, value: Any
) -> bool:
    """Handle options marimo applies after per-file reads are decoded."""
    if key == "filename" and isinstance(value, bool | str):
        options["filename"] = value
        return True
    if key == "union_by_name" and isinstance(value, bool):
        options["union_by_name"] = value
        return True
    return False


def _apply_compression_option(
    options: dict[str, Any], key: str, value: Any
) -> bool:
    """Accept only compression modes supported by the byte-fetch fallback."""
    if key == "compression" and _is_supported_compression(value):
        options["compression"] = str(value).lower()
        return True
    return False


def _apply_shared_source_option(
    options: dict[str, Any], key: str, value: Any
) -> bool:
    """Apply source options shared by CSV, parquet, and JSON fallbacks."""
    return _apply_compression_option(
        options, key, value
    ) or _apply_common_table_option(options, key, value)


def _is_supported_compression(value: Any) -> bool:
    """Limit compression to modes the fallback knows how to preserve."""
    return str(value).lower() in {"auto", "none", "gzip"}
