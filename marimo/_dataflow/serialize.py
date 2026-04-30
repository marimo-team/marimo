# Copyright 2026 Marimo. All rights reserved.
"""Serialize Python values for the dataflow wire protocol."""

from __future__ import annotations

import base64
from typing import Any

from marimo._dataflow.protocol import Kind


def infer_kind(value: Any) -> Kind:
    """Infer the Kind for a Python value."""
    if value is None:
        return Kind.NULL
    if isinstance(value, bool):
        return Kind.BOOLEAN
    if isinstance(value, int):
        return Kind.INTEGER
    if isinstance(value, float):
        return Kind.NUMBER
    if isinstance(value, str):
        return Kind.STRING
    if isinstance(value, bytes):
        return Kind.BYTES
    if isinstance(value, list):
        return Kind.LIST
    if isinstance(value, dict):
        return Kind.DICT
    if isinstance(value, tuple):
        return Kind.TUPLE

    type_name = type(value).__name__
    module = type(value).__module__

    if type_name == "DataFrame" or module.startswith(
        ("pandas", "polars", "pyarrow")
    ):
        return Kind.TABLE
    if type_name == "ndarray" and module.startswith("numpy"):
        return Kind.TENSOR

    return Kind.ANY


def serialize_value(
    value: Any,
    encoding: str = "json",
) -> tuple[Any, str | None]:
    """Serialize a value for the wire.

    Returns:
        (inline_value, blob_ref) — one of these will be non-None.
        If blob_ref is set, the value is too large for inline and should
        be served at that ref URL.
    """
    if encoding == "json":
        return _to_json(value), None
    if encoding == "arrow_ipc":
        return None, _to_arrow_ipc_ref(value)
    # Default: attempt JSON
    return _to_json(value), None


def _to_json(value: Any) -> Any:
    """Convert a Python value to a JSON-compatible form."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (list, tuple)):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json(v) for k, v in value.items()}

    # DataFrame-like objects
    type_name = type(value).__name__
    module = type(value).__module__

    if type_name == "DataFrame":
        if module.startswith("pandas"):
            return value.to_dict(orient="records")
        if module.startswith("polars"):
            return value.to_dicts()

    # numpy
    if type_name == "ndarray" and module.startswith("numpy"):
        return value.tolist()

    # Fallback: repr
    try:
        return repr(value)
    except Exception:
        return f"<{type_name}>"


def _to_arrow_ipc_ref(value: Any) -> str:
    """Serialize a table to Arrow IPC and return a blob reference.

    For now this returns inline base64; in Phase 2 we'll use the
    virtual file system for large payloads.
    """
    import pyarrow as pa

    type_name = type(value).__name__
    module = type(value).__module__

    table: pa.Table
    if type_name == "DataFrame" and module.startswith("pandas"):
        table = pa.Table.from_pandas(value)
    elif type_name == "DataFrame" and module.startswith("polars"):
        table = value.to_arrow()
    elif isinstance(value, pa.Table):
        table = value
    else:
        raise TypeError(
            f"Cannot serialize {type_name} as Arrow IPC. "
            "Expected a pandas/polars DataFrame or pyarrow Table."
        )

    sink = pa.BufferOutputStream()
    writer = pa.ipc.new_stream(sink, table.schema)
    writer.write_table(table)
    writer.close()
    buf = sink.getvalue()
    return (
        "data:application/vnd.apache.arrow.stream;base64,"
        + base64.b64encode(buf.to_pybytes()).decode("ascii")
    )
