# Copyright 2026 Marimo. All rights reserved.
"""Value classification and artifact writers for the build pipeline.

A defined value can be persisted as one of two artifact kinds:

- ``"dataframe"`` -> parquet, written via narwhals -> the value's
  native engine (polars, pandas, pyarrow, ...).
- ``"json"`` -> JSON file, written via the stdlib ``json`` module.

Anything else returns ``None`` from :func:`classify_value`, which
signals to the build that the cell can't be compiled.

Extending the build to support new artifact kinds is a matter of
adding a branch here and a matching loader template in
:mod:`marimo._build.codegen`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

ArtifactKind = Literal["dataframe", "json"]


def classify_value(value: Any) -> ArtifactKind | None:
    """Determine the artifact kind for a defined value, or None.

    Order matters: dataframes can technically be JSON-serializable
    via their string repr, but we prefer parquet for fidelity.
    """
    if _is_dataframe(value):
        return "dataframe"
    if _is_json_serializable(value):
        return "json"
    return None


def write_artifact(value: Any, path: Path, kind: ArtifactKind) -> None:
    """Persist ``value`` to ``path`` according to ``kind``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "dataframe":
        _write_parquet(value, path)
    elif kind == "json":
        path.write_text(json.dumps(value), encoding="utf-8")
    else:  # pragma: no cover - guarded by the Literal
        raise ValueError(f"Unknown artifact kind: {kind!r}")


def _is_dataframe(value: Any) -> bool:
    import narwhals.stable.v1 as nw

    try:
        nw.from_native(value, pass_through=False)
        return True
    except (TypeError, AttributeError):
        return False


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def _write_parquet(value: Any, path: Path) -> None:
    """Write a narwhals-compatible dataframe to ``path`` as parquet.

    narwhals' ``write_parquet`` works for polars and pyarrow-backed
    frames out of the box. For other backends — DuckDB (``mo.sql``'s
    native return type) in particular — we fall back to the underlying
    object's own writer. The probe order is:

    1. narwhals ``write_parquet``;
    2. native ``write_parquet`` (polars, DuckDB);
    3. native ``to_parquet``    (pandas, DuckDB);
    4. native ``sink_parquet``  (polars LazyFrames).
    """
    import narwhals.stable.v1 as nw

    df = nw.from_native(value, pass_through=False)
    if hasattr(df, "collect"):
        df = df.collect()

    target = str(path)
    try:
        df.write_parquet(target)
        return
    except AttributeError:
        # narwhals wraps some backends (e.g. DuckDB) such that the
        # narwhals-level write_parquet exists but the underlying
        # compliant frame doesn't implement it. Fall through to native.
        pass

    native = df.to_native()
    for method in ("write_parquet", "to_parquet", "sink_parquet"):
        write = getattr(native, method, None)
        if write is not None:
            write(target)
            return
    raise RuntimeError(
        f"Cannot write parquet for dataframe of type {type(value).__name__}; "
        "install pyarrow or use a polars/pyarrow-backed frame."
    )
