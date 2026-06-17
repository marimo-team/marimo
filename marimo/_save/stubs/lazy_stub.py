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

    from marimo._runtime.exceptions import MarimoUnhashableCacheError


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
    # (module, qualname) of a value re-importable by name — e.g.
    # `from typing import Optional` or `from os.path import join`. Stored
    # inline so trivial imported references never get their own blob on disk.
    import_ref: tuple[str, str] | None = None
    # (code, filename, linenumber)
    function: tuple[str, str, int] | None = None
    # (code, filename, linenumber, qualname) — cell-defined class source.
    # Materialized into the cell namespace before pickle blobs deserialize,
    # so __main__-qualified instances can resolve their type.
    class_def: tuple[str, str, int, str] | None = None
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
                self.import_ref,
                self.function,
                self.class_def,
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
#   "pt"      — torch .pt blob (torch.save / torch.load)
LAZY_STUB_LOOKUP: dict[str, str] = {
    "builtins.int": "inline",
    "builtins.str": "inline",
    "builtins.float": "inline",
    "builtins.bool": "inline",
    # bytes can't round-trip through JSON (msgspec encodes as base64
    # but decodes back as str with Any type). Use pickle instead.
    "builtins.bytes": "pickle",
    "builtins.NoneType": "inline",
    "marimo._save.stubs.function_stub.FunctionStub": "inline",
    "marimo._save.stubs.class_stub.ClassStub": "inline",
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
    # Subclasses (e.g. torch.nn.Parameter) resolve here through the MRO
    # walk in maybe_update_lazy_stub; torch.save round-trips them intact.
    "torch.Tensor": "pt",
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


def _pt_load(data: bytes, type_hint: str | None = None) -> Any:
    DependencyManager.torch.require("to load cached torch tensors.")
    import torch  # type: ignore[import-not-found]

    del type_hint
    # weights_only restricts unpickling to tensor payloads; a tensor saved
    # on an unavailable device fails loudly here, and the cache falls back
    # to recomputation rather than silently relocating the value.
    return torch.load(io.BytesIO(data), weights_only=True)


def _pickle_load(data: bytes, type_hint: str | None = None) -> Any:
    del type_hint
    return pickle.loads(data)


BLOB_DESERIALIZERS: dict[str, Callable[[bytes, str | None], Any]] = {
    ".pickle": _pickle_load,
    ".npy": _npy_load,
    ".arrow": _arrow_load,
    ".pt": _pt_load,
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


def _pt_dump(obj: Any) -> bytes:
    DependencyManager.torch.require("to dump torch tensors.")
    import torch  # type: ignore[import-not-found]

    buf = io.BytesIO()
    torch.save(obj, buf)
    return buf.getvalue()


BLOB_SERIALIZERS: dict[str, Callable[[Any], bytes]] = {
    "pickle": pickle.dumps,
    "npy": _npy_dump,
    "arrow": _arrow_dump,
    "pt": _pt_dump,
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


class UnhashableStub(CustomStub):
    """Marker + tripwire for a def that could not be serialized for caching.

    Written to the cache as a placeholder when per-def pickling fails (e.g.
    a lambda, a closure over an unpicklable object). The marker is placed
    in scope as-is by `Cache.restore` (no `.load()` call). It is
    harmless when the consumer cell never touches it; any meaningful access
    (call) raises `MarimoUnhashableCacheError` carrying
    `variables=[var_name]` so the runner can identify the defining cell,
    invalidate its manifest, and re-queue.

    Detection happens at use-site, not at pre-execution. Bodies that don't
    touch the stub run normally; closure-captured stubs surface through
    whichever access the user code performs.

    UnhashableStub is created on-demand by the loader and is not
    registered in CUSTOM_STUBS — `get_type()` raises since no specific
    value type maps to it.

    `__marimo_unhashable__` is a class-level protocol marker: runtime
    consumers (e.g. a cached-execution pre-flight) detect stubs through
    the attribute rather than importing this class, keeping the runtime
    and serialization layers independently mergeable.
    """

    __marimo_unhashable__ = True

    __slots__ = ("error_msg", "type_name", "var_name")

    def __init__(
        self,
        _obj: Any = None,
        var_name: str = "",
        error_msg: str = "",
    ) -> None:
        self.var_name = var_name
        if _obj is not None:
            value_type = type(_obj)
            self.type_name = (
                f"{getattr(value_type, '__module__', '<unknown>')}."
                f"{getattr(value_type, '__name__', '<unknown>')}"
            )
        else:
            self.type_name = "<unknown>"
        self.error_msg = error_msg or "value could not be pickled for cache"

    def _trip(self) -> MarimoUnhashableCacheError:
        from marimo._runtime.exceptions import MarimoUnhashableCacheError

        return MarimoUnhashableCacheError(
            cells_to_rerun=set(),
            variables=[self.var_name] if self.var_name else [],
            error_details=(
                f"{self.var_name} ({self.type_name}): {self.error_msg}"
                if self.var_name
                else f"({self.type_name}): {self.error_msg}"
            ),
        )

    def load(self, glbls: dict[str, Any]) -> Any:
        del glbls
        raise self._trip()

    # __call__ is the only tripwire: it covers the canonical user-code
    # use pattern (`classic(x)`, `foo()` where foo's closure captures
    # the stub) that produces `'UnhashableStub' object is not callable`.
    # Other dunders (__getattr__, __getitem__, __iter__, __len__, …)
    # deliberately fall through to Python defaults so framework probes
    # (`getattr(value, "_repr_mimebundle_", None)`, isinstance, hasattr,
    # storage-engine introspection, etc.) stay inert. A body that uses
    # the stub through a non-call access raises a generic TypeError
    # instead of the cleaner trip — acceptable trade-off; the alternative
    # over-trips on framework probes and cancels innocent cells.
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise self._trip()

    def __repr__(self) -> str:
        return (
            f"<UnhashableStub var_name={self.var_name!r} "
            f"type={self.type_name!r}>"
        )

    @staticmethod
    def get_type() -> type:
        # UnhashableStub does not correspond to a specific value type — it's
        # written on-demand by the loader when pickling fails. Not registered
        # in CUSTOM_STUBS.
        raise NotImplementedError(
            "UnhashableStub is not registered for a specific type"
        )

    def to_bytes(self) -> bytes:
        return pickle.dumps(self)
