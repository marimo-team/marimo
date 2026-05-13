# Copyright 2026 Marimo. All rights reserved.
"""WASM-only fallback patches for polars.

Two flavors of fallback live here, both built on :class:`WasmPatchSet`:

* **Read/scan I/O** — in pyodide, polars' Rust core can't reach the network
  and its Python fallbacks reference missing modules (fsspec/aiohttp),
  surfacing as :class:`NameError` and friends. On failure we resolve the
  source to bytes, decode via pyarrow, and convert with
  :func:`polars.from_arrow`.

* **DataFrame.write_json** — file system / native JSON writers can fail in
  WASM. On failure we round-trip via CSV and emit JSON manually.

Read/scan path is best-effort: polars-only kwargs (``n_rows``,
``try_parse_dates``, ...) are ignored; common kwargs with a pyarrow
equivalent (``columns``, csv ``separator``, ``has_header``) are honored.
All patches are no-ops outside pyodide.
"""

from __future__ import annotations

import io
import pathlib
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._runtime._wasm import _fetch
from marimo._runtime._wasm._patches import Unpatch, WasmPatchSet
from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from collections.abc import Callable

    import polars as pl

LOGGER = _loggers.marimo_logger()


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------


def _is_url(source: Any) -> bool:
    return isinstance(source, str) and source.startswith(
        ("http://", "https://")
    )


def _resolve_to_bytes(source: Any) -> bytes:
    """Coerce a polars I/O source into raw bytes."""
    if isinstance(source, bytes):
        return source
    if isinstance(source, bytearray):
        return bytes(source)
    if isinstance(source, io.IOBase):
        data = source.read()
        if isinstance(data, str):
            return data.encode("utf-8")
        return data  # type: ignore[no-any-return]
    if isinstance(source, pathlib.Path):
        return source.read_bytes()
    if isinstance(source, str):
        if _is_url(source):
            return _fetch.fetch_url_bytes(source)
        return pathlib.Path(source).read_bytes()
    raise TypeError(
        f"Unsupported source type for WASM polars fallback: {type(source)!r}"
    )


# ---------------------------------------------------------------------------
# pyarrow decoders
# ---------------------------------------------------------------------------


def _read_csv_arrow(buf: io.BytesIO, **kwargs: Any) -> Any:
    import pyarrow.csv as pa_csv  # type: ignore[import-not-found]

    read_options = pa_csv.ReadOptions(
        autogenerate_column_names=not kwargs.get("has_header", True),
    )
    parse_options_kwargs: dict[str, Any] = {}
    if "separator" in kwargs:
        parse_options_kwargs["delimiter"] = kwargs["separator"]
    parse_options = pa_csv.ParseOptions(**parse_options_kwargs)
    convert_options_kwargs: dict[str, Any] = {}
    if "columns" in kwargs and kwargs["columns"] is not None:
        convert_options_kwargs["include_columns"] = list(kwargs["columns"])
    convert_options = pa_csv.ConvertOptions(**convert_options_kwargs)
    return pa_csv.read_csv(
        buf,
        read_options=read_options,
        parse_options=parse_options,
        convert_options=convert_options,
    )


def _read_parquet_arrow(buf: io.BytesIO, **kwargs: Any) -> Any:
    import pyarrow.parquet as pa_parquet  # type: ignore[import-not-found]

    read_kwargs: dict[str, Any] = {}
    if "columns" in kwargs and kwargs["columns"] is not None:
        read_kwargs["columns"] = list(kwargs["columns"])
    return pa_parquet.read_table(buf, **read_kwargs)


def _read_ipc_arrow(buf: io.BytesIO, **kwargs: Any) -> Any:
    import pyarrow.feather as pa_feather  # type: ignore[import-not-found]

    read_kwargs: dict[str, Any] = {}
    if "columns" in kwargs and kwargs["columns"] is not None:
        read_kwargs["columns"] = list(kwargs["columns"])
    return pa_feather.read_table(buf, **read_kwargs)


def _read_json_arrow(buf: io.BytesIO, **kwargs: Any) -> Any:
    del kwargs
    import pyarrow.json as pa_json  # type: ignore[import-not-found]

    return pa_json.read_json(buf)


_ARROW_READERS: dict[str, Callable[..., Any]] = {
    "csv": _read_csv_arrow,
    "parquet": _read_parquet_arrow,
    "ipc": _read_ipc_arrow,
    "ndjson": _read_json_arrow,
    "json": _read_json_arrow,
}


# ---------------------------------------------------------------------------
# Fallback factory
# ---------------------------------------------------------------------------


def _make_fallback(fmt: str, lazy: bool) -> Callable[..., Any]:
    """Decode ``source`` via pyarrow and return polars."""
    import polars as pl

    from marimo._dependencies.dependencies import DependencyManager

    reader = _ARROW_READERS[fmt]

    def _fallback(
        original: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        DependencyManager.pyarrow.require(
            f"to read polars {fmt} sources in WASM"
        )
        del original
        if not args:
            source = kwargs.pop("source", None)
            if source is None:
                # polars renames the first arg across versions.
                for alt in ("file", "path"):
                    if alt in kwargs:
                        source = kwargs.pop(alt)
                        break
            if source is None:
                raise TypeError("Missing source argument")
            rest_args: tuple[Any, ...] = ()
        else:
            source, rest_args = args[0], args[1:]
        del rest_args  # polars-specific positional args aren't forwarded

        data = _resolve_to_bytes(source)
        table = reader(io.BytesIO(data), **kwargs)
        df: pl.DataFrame = pl.from_arrow(table)  # type: ignore[assignment]
        # scan_* materializes eagerly; true streaming wouldn't work in WASM.
        return df.lazy() if lazy else df

    return _fallback


# ---------------------------------------------------------------------------
# write_json fallback
# ---------------------------------------------------------------------------


def _write_json_fallback(
    _original: Callable[..., Any],
    self: pl.DataFrame,
    file: Any = None,
    *_args: Any,
    **_kwargs: Any,
) -> str | None:
    """Convert the frame to dicts and emit JSON.

    ``to_dicts`` preserves types and handles quoting/embedded delimiters
    correctly (unlike a naive CSV split), and avoids I/O so it works in WASM.
    ``default=str`` covers temporal/decimal types that aren't JSON-native.
    """
    import json

    json_data = self.to_dicts()

    if file is None:
        return json.dumps(json_data, default=str)
    if isinstance(file, io.IOBase):
        json.dump(json_data, file, default=str)
    elif isinstance(file, pathlib.Path):
        file.write_text(json.dumps(json_data, default=str))
    else:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, default=str)
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


# (polars attr, format key, lazy)
_IO_TARGETS: tuple[tuple[str, str, bool], ...] = (
    ("read_csv", "csv", False),
    ("scan_csv", "csv", True),
    ("read_parquet", "parquet", False),
    ("scan_parquet", "parquet", True),
    ("read_ipc", "ipc", False),
    ("scan_ipc", "ipc", True),
    ("read_ndjson", "ndjson", False),
    ("scan_ndjson", "ndjson", True),
    ("read_json", "json", False),
)


def patch_polars_for_wasm() -> Unpatch:
    """Install all WASM fallbacks for polars (read/scan I/O + write_json)."""
    if not is_pyodide():
        return lambda: None

    try:
        import polars as pl
    except ImportError:
        return lambda: None

    patches = WasmPatchSet()

    for attr, fmt, lazy in _IO_TARGETS:
        if not hasattr(pl, attr):
            continue
        try:
            fallback = _make_fallback(fmt, lazy)
        except Exception as e:
            LOGGER.warning(
                "Failed to build WASM fallback for polars.%s: %s", attr, e
            )
            continue
        patches.patch(pl, attr, fallback)

    patches.patch(pl.DataFrame, "write_json", _write_json_fallback)

    return patches.unpatch_all()
