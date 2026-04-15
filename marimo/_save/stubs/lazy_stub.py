# Copyright 2026 Marimo. All rights reserved.
"""msgspec schemas and format registries for lazy cache serialization."""

from __future__ import annotations

import io
import pickle
from enum import Enum
from typing import TYPE_CHECKING, Any

import msgspec

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.stores import get_store
from marimo._save.stubs.stubs import CustomStub

if TYPE_CHECKING:
    from collections.abc import Callable


class CacheType(Enum):
    CONTEXT_EXECUTION_PATH = "ContextExecutionPath"
    CONTENT_ADDRESSED = "ContentAddressed"
    EXECUTION_PATH = "ExecutionPath"
    PURE = "Pure"
    DEFERRED = "Deferred"
    UNKNOWN = "Unknown"


class Item(msgspec.Struct):
    """Represents a cached item with different value types.

    Only one of the value fields should be set (oneof semantics).
    """

    primitive: Any | None = None
    reference: str | None = None
    module: str | None = None
    # (code, filename, linenumber)
    function: tuple[str, str, int] | None = None
    hash: str | None = None
    # Fully-qualified class name of the original value — used by format-aware
    # deserializers (e.g. to distinguish pandas from polars Arrow blobs).
    type_hint: str | None = None

    def __post_init__(self) -> None:
        fields_set = sum(
            1
            for field in [
                self.primitive,
                self.reference,
                self.module,
                self.function,
            ]
            if field is not None
        )
        if fields_set > 1:
            raise ValueError("Item can only have one value field set")


class Meta(msgspec.Struct):
    version: int
    return_value: Item | None = None


class Cache(msgspec.Struct):
    hash: str
    cache_type: CacheType
    defs: dict[str, Item]
    stateful_refs: list[str]
    meta: Meta
    ui_defs: list[str] = msgspec.field(default_factory=list)


# ---------------------------------------------------------------------------
# Unified type-to-loader registry
# ---------------------------------------------------------------------------

# Maps fully-qualified class names to loader strategy strings.
# String keys mean optional deps (numpy, polars, pandas) are never imported at
# module load time — they are only imported when the serializer/deserializer
# is actually called.
#
# Strategies:
#   "inline"  — stored as a primitive/function/module field in the Item struct
#   "ui"      — shared ui.pickle blob (UIElement family)
#   "pickle"  — per-variable .pickle blob (default fallback)
#   "npy"     — numpy .npy blob
#   "arrow"   — Arrow IPC .arrow blob (polars and pandas)
LAZY_STUB_LOOKUP: dict[str, str] = {
    "builtins.int": "inline",
    "builtins.str": "inline",
    "builtins.float": "inline",
    "builtins.bool": "inline",
    "builtins.bytes": "inline",
    "builtins.NoneType": "inline",
    "marimo._save.stubs.function_stub.FunctionStub": "inline",
    "marimo._save.stubs.module_stub.ModuleStub": "inline",
    "marimo._save.stubs.ui_element_stub.UIElementStub": "ui",
    # Optional third-party types — imported lazily only when encountered:
    "numpy.ndarray": "npy",
    "polars.dataframe.frame.DataFrame": "arrow",
    "polars.series.series.Series": "arrow",
    # pandas 3.x sets __module__ = "pandas"; 2.x exposes the internal path
    "pandas.DataFrame": "arrow",
    "pandas.core.frame.DataFrame": "arrow",
    "pandas.Series": "arrow",
    "pandas.core.series.Series": "arrow",
}

# Runtime cache: type → loader string, populated by maybe_update_lazy_stub().
_LAZY_STUB_CACHE: dict[type, str] = {}

# ---------------------------------------------------------------------------
# Deserializers — keyed by file extension
# ---------------------------------------------------------------------------


def _npy_load(data: bytes, type_hint: str | None = None) -> Any:
    DependencyManager.numpy.require("to load cached numpy arrays.")
    import numpy as np

    del type_hint
    return np.load(io.BytesIO(data), allow_pickle=True)


def _arrow_load(data: bytes, type_hint: str | None = None) -> Any:
    # type_hint is the fq class name written by to_item() at save time.
    # Using it (rather than schema metadata inspection) is explicit and
    # version-stable across pyarrow/polars/pandas releases.
    DependencyManager.pyarrow.require("to load cached Arrow IPC blobs.")
    import pyarrow as pa

    reader = pa.ipc.open_file(io.BytesIO(data))
    table = reader.read_all()
    if type_hint and type_hint.startswith("pandas."):
        df = table.to_pandas()
        if type_hint in ("pandas.Series", "pandas.core.series.Series"):
            # Stored as a single-column DataFrame; recover as a Series.
            return df.iloc[:, 0]
        return df
    import polars as pl

    result = pl.from_arrow(table)
    if type_hint == "polars.series.series.Series":
        # Stored as a single-column DataFrame; recover as a Series.
        if isinstance(result, pl.DataFrame):
            return result.to_series(0)
        return result
    return result


def _pickle_load(data: bytes, type_hint: str | None = None) -> Any:
    del type_hint
    return pickle.loads(data)


BLOB_DESERIALIZERS: dict[str, Callable[[bytes, str | None], Any]] = {
    ".pickle": _pickle_load,
    ".npy": _npy_load,
    ".arrow": _arrow_load,
}

# ---------------------------------------------------------------------------
# Serializers — keyed by loader strategy string
# ---------------------------------------------------------------------------


def _npy_dump(obj: Any) -> bytes:
    DependencyManager.numpy.require("to save numpy arrays to cache.")
    import numpy as np

    buf = io.BytesIO()
    np.save(buf, obj)
    return buf.getvalue()


def _arrow_dump(obj: Any) -> bytes:
    # Duck-type dispatch:
    #   polars DataFrame  → write_ipc()
    #   pandas DataFrame  → to_feather()
    #   Series (either)   → to_frame() first, then the appropriate DataFrame method
    # Fall back to pickle when pyarrow is absent so the cache write never fails.
    if not DependencyManager.pyarrow.has():
        return pickle.dumps(obj)
    buf = io.BytesIO()
    if hasattr(obj, "write_ipc"):  # polars DataFrame
        obj.write_ipc(buf)
    elif hasattr(obj, "to_feather"):  # pandas DataFrame
        obj.to_feather(buf)
    else:
        # Series — promote to single-column DataFrame, then detect library
        frame = obj.to_frame()
        if hasattr(frame, "write_ipc"):  # polars Series → polars DataFrame
            frame.write_ipc(buf)
        else:  # pandas Series → pandas DataFrame
            frame.to_feather(buf)
    return buf.getvalue()


BLOB_SERIALIZERS: dict[str, Callable[[Any], bytes]] = {
    "pickle": pickle.dumps,
    "npy": _npy_dump,
    "arrow": _arrow_dump,
}

# ---------------------------------------------------------------------------
# Stubs for deferred / immediate blob loading
# ---------------------------------------------------------------------------


class ReferenceStub:
    """Deferred blob reference — loads from store on access."""

    def __init__(
        self, name: str, loader: str | None = None, hash_value: str = ""
    ) -> None:
        self.name = name
        self.loader = loader
        self.hash = hash_value

    def load(self, glbls: dict[str, Any]) -> Any:
        del glbls
        blob = self.to_bytes()
        if not blob:
            raise ValueError(f"Reference {self.name} not found in store.")
        return pickle.loads(blob)

    def to_bytes(self) -> bytes:
        maybe_bytes = get_store().get(self.name)
        return maybe_bytes if maybe_bytes else b""


class ImmediateReferenceStub(CustomStub):
    """Wraps a ReferenceStub for immediate return-value restoration."""

    def __init__(self, reference: ReferenceStub) -> None:
        self.reference = reference

    def load(self, glbls: dict[str, Any]) -> Any:
        return self.reference.load(glbls)

    @staticmethod
    def get_type() -> type:
        return ReferenceStub

    def to_bytes(self) -> bytes:
        return self.reference.to_bytes()
