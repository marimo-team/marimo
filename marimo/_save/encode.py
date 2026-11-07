# Copyright 2026 Marimo. All rights reserved.
"""Deterministic encoding of Python values to bytes for content-addressed hashing.

This module owns the conversion of Python objects (primitives, tensors,
containers, arbitrary picklable objects) into canonical byte sequences.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import io
import itertools
import numbers
import pickle
import struct
from typing import TYPE_CHECKING, Any

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.primitives import is_data_primitive, is_primitive

if TYPE_CHECKING:
    from collections.abc import Iterable

    # Union[torch.Tensor, jax.numpy.ndarray,
    #             np.ndarray, scipy.sparse.spmatrix]
    Tensor = Any


def _frame(label: str, size: int) -> bytes:
    tag = label.encode("utf-8")
    return b"".join(
        [struct.pack("!Q", len(tag)), tag, struct.pack("!Q", size)]
    )


def type_sign(value: bytes | memoryview, label: str) -> bytes:
    """Frame a typed payload without losing boundaries between values."""
    # Tagging values disambiguates types, for example when a string contains
    # the same bytes as a packed float or is the literal ":none".
    # Length prefixes also preserve boundaries between adjacent values.
    #
    # This does not protect against cache poisoning by an attacker who controls
    # the store. Cache signatures authenticate stored bytes independently of
    # the key encoding, and neither protects a compromised Python runtime.
    #
    # TODO: Benchmark this encoding, including the cost of copying large data.
    # len(memoryview) counts the first dimension, not the number of bytes.
    size = value.nbytes if isinstance(value, memoryview) else len(value)
    return _frame(label, size) + value


_LENGTH = struct.Struct("!Q")


def iterable_sign(value: Iterable[Any], label: str) -> bytes:
    # An item count alone cannot tell apart different ways to divide the same
    # bytes among the items, so prefix each item with its length. On 1e5 to
    # 1e6 element containers, per-item type_sign framing measured about 35%
    # slower than an unframed join. Length prefixes alone measured about 19%
    # slower.
    pack = _LENGTH.pack
    return type_sign(
        b"".join(
            itertools.chain.from_iterable(
                (pack(len(item)), item) for item in value
            )
        ),
        label,
    )


def standardize_tensor(tensor: Tensor) -> Tensor:
    if (
        hasattr(tensor, "__array__")
        or hasattr(tensor, "toarray")
        or hasattr(tensor, "__array_interface__")
    ):
        DependencyManager.numpy.require("to access data buffer for hashing.")
        import numpy

        if not hasattr(tensor, "__array_interface__"):
            # Capture those sparse cases
            if hasattr(tensor, "toarray"):
                tensor = tensor.toarray()
        # As array should not perform copy
        return numpy.asarray(tensor)
    raise ValueError(
        f"Expected a data primitive object, but got {type(tensor)} instead."
        "This maybe is an internal marimo issue. Please report to "
        "https://github.com/marimo-team/marimo/issues."
    )


def _contiguous_tensor_bytes(data: Tensor) -> memoryview:
    """Return a contiguous uint8 view of a tensor/array."""
    data = standardize_tensor(data)
    # From joblib.hashing
    if data.shape == ():
        # 0d arrays need to be flattened because viewing them as bytes
        # raises a ValueError exception.
        data_c_contiguous = data.flatten()
    elif data.flags.c_contiguous:
        data_c_contiguous = data
    elif data.flags.f_contiguous:
        data_c_contiguous = data.T
    else:
        # Cater for non-single-segment arrays, this creates a copy, and thus
        # alleviates this issue. Note: There might be a more efficient way of
        # doing this, check for joblib updates.
        data_c_contiguous = data.flatten()
    return memoryview(data_c_contiguous.view("uint8"))


def data_frames(data: Tensor) -> tuple[bytes, memoryview]:
    """Framed metadata header and the raw buffer of an array-like."""
    array = standardize_tensor(data)
    # str(dtype) keeps byte order, subarray shapes and field offsets, and does
    # not raise on overlapping or out-of-order fields the way dtype.descr does.
    metadata = primitive_to_bytes(
        (
            type(data).__module__,
            type(data).__qualname__,
            str(array.dtype),
            array.shape,
            array.strides,
        )
    )
    buffer = _contiguous_tensor_bytes(array)
    header = type_sign(metadata, "array") + _frame("data", buffer.nbytes)
    return header, buffer


def data_to_buffer(data: Tensor) -> bytes:
    header, buffer = data_frames(data)
    return header + buffer


def primitive_to_bytes(value: Any) -> bytes:
    if value is None:
        return type_sign(b"", "none")
    if value is Ellipsis:
        return type_sign(b"", "ellipsis")
    if type(value) is bool:
        return type_sign(bytes([value]), "bool")
    if isinstance(value, str):
        return type_sign(value.encode("utf-8"), "str")
    if type(value) is float:
        return type_sign(struct.pack("!d", value), "float")
    if type(value) is int:
        size = (value.bit_length() + 8) // 8
        return type_sign(value.to_bytes(size, "big", signed=True), "int")
    if type(value) is complex:
        return type_sign(struct.pack("!dd", value.real, value.imag), "complex")
    if type(value) is bytes:
        return type_sign(value, "bytes")
    if type(value) is tuple:
        return iterable_sign(map(primitive_to_bytes, value), "tuple")
    # A numpy scalar holds its width and byte order in its dtype, so
    # np.int64(2), np.int32(2), 2 and bytes(2) encode differently.
    dtype = getattr(value, "dtype", None)
    if dtype is not None and hasattr(value, "tobytes"):
        return type_sign(
            primitive_to_bytes((str(dtype), value.tobytes())), "numpy"
        )
    # bytes(n) on an int subclass allocates n zero bytes, and a subclass can
    # override repr lossily, so a Number subclass is keyed by its type and the
    # exact value its numeric tower exposes. Decimal is only a Number, and its
    # repr is exact.
    if isinstance(value, numbers.Number):
        base: Any
        if isinstance(value, numbers.Integral):
            base = int(value)
        elif isinstance(value, numbers.Rational):
            base = (int(value.numerator), int(value.denominator))
        elif isinstance(value, numbers.Real):
            base = float(value)
        elif isinstance(value, numbers.Complex):
            base = complex(value)
        else:
            base = repr(value)
        cls = type(value)
        return type_sign(
            primitive_to_bytes((cls.__module__, cls.__qualname__, base)),
            "scalar",
        )
    return type_sign(bytes(value), "bytes")


def common_container_to_bytes(value: Any) -> bytes:
    visited: dict[int, int] = {}

    def recurse_container(value: Any) -> bytes:
        if id(value) in visited:
            return type_sign(bytes(visited[id(value)]), "id")
        if isinstance(value, dict):
            visited[id(value)] = len(visited)
            return iterable_sign(map(recurse_container, value.items()), "dict")
        if isinstance(value, list):
            visited[id(value)] = len(visited)
            return iterable_sign(map(recurse_container, value), "list")
        if isinstance(value, set):
            visited[id(value)] = len(visited)
            return iterable_sign(sorted(map(recurse_container, value)), "set")
        # Tuple may be only data primitive, not fully primitive.
        if isinstance(value, tuple):
            return iterable_sign(map(recurse_container, value), "tuple")
        # bytearray is mutable so not in PRIMITIVES, but its bytes are a
        # deterministic content key; sign under a distinct label so it does not
        # collide with an equal-content bytes value.
        if isinstance(value, bytearray):
            return type_sign(bytes(value), "bytearray")

        if is_primitive(value):
            return primitive_to_bytes(value)
        if is_data_primitive(value):
            return data_to_buffer(value)
        raise TypeError(
            f"Expected numeric array data, got {type(value).__name__}"
        )

    return recurse_container(value)


def attempt_signed_bytes(value: bytes, label: str) -> bytes:
    # Prevents hash collisions like:
    # >>> fib(1)
    # >>> s, _ = state(1)
    # >>> fib(s)
    # ^ would be a cache hit as is even though fib(s) would fail by
    # itself
    try:
        return type_sign(common_container_to_bytes(value), label)
    # Fallback to raw state for eval in content hash.
    except (TypeError, ValueError):
        return value


@dataclasses.dataclass
class HashState:
    """State shared by every pickler of one key computation."""

    # By id, with the object kept alive beside its entry: a temporary from
    # `__getstate__` can be freed and its id reused within one computation.
    #
    # A function's fingerprint, or None while it is being computed, so a
    # closure over itself terminates and a revisit contributes the same bytes.
    functions: dict[int, tuple[Any, bytes | None]] = dataclasses.field(
        default_factory=dict
    )
    # Ordering key of a set member, computed once per key computation.
    member_keys: dict[int, tuple[Any, bytes]] = dataclasses.field(
        default_factory=dict
    )
    # Sets whose members are being ordered right now.
    ordering: set[int] = dataclasses.field(default_factory=set)


def deterministic_dumps(
    obj: Any, hash_type: str, _seen: HashState | None = None
) -> bytes:
    """`pickle.dumps` replacement that produces more deterministic bytes."""
    from marimo._save.hash import hash_wrapped_functions
    from marimo._save.stubs import maybe_get_custom_stub

    state = HashState() if _seen is None else _seen

    class _ContentHashPickler(pickle.Pickler):
        # Sets already encoded by this pickler, so a second reference to the
        # same set is an alias and not a copy, as pickle's memo would record.
        # The set is kept alive beside its index.
        _sets: dict[int, tuple[Any, int]]

        def persistent_id(self, obj: Any) -> Any:
            # The pickler never asks `reducer_override` about a set, but it
            # asks `persistent_id` about everything. Iteration order of a set
            # follows hash randomization, so stand in an id that orders the
            # members by their own encoding. The members themselves still go
            # through this pickler, so aliases with the surrounding value
            # survive. The output is hashed, never loaded, so the id need not
            # resolve.
            if type(obj) not in (set, frozenset):
                return None
            if id(obj) in state.ordering:
                # Reached again while ordering its own members.
                return ("set-cycle",)
            sets = self.__dict__.setdefault("_sets", {})
            if id(obj) in sets:
                return ("set-alias", sets[id(obj)][1])
            index = len(sets)
            sets[id(obj)] = (obj, index)
            state.ordering.add(id(obj))
            try:
                for item in obj:
                    if id(item) not in state.member_keys:
                        state.member_keys[id(item)] = (
                            item,
                            deterministic_dumps(item, hash_type, _seen=state),
                        )
            finally:
                state.ordering.discard(id(obj))
            members = sorted(
                obj, key=lambda item: state.member_keys[id(item)][1]
            )
            return (type(obj).__name__, index, tuple(members))

        def reducer_override(self, obj: Any) -> Any:
            if stub := maybe_get_custom_stub(obj):
                return (bytes, (stub.to_bytes(),))
            if inspect.isfunction(obj):
                # Pickle stores a function by reference, so an edit to a
                # callback held inside a value would not change the key.
                # Fingerprint it by content, and reduce to plain bytes: a
                # function-valued reduce callable gets fingerprinted in turn.
                try:
                    fingerprint = hash_wrapped_functions(
                        obj, hash_type, _seen=state
                    )
                except Exception:
                    # By reference, as pickle would.
                    return NotImplemented
                if getattr(obj, "__module__", None) == "__main__":
                    # A notebook function's globals are not in its
                    # fingerprint, and inside a value no graph accounts for
                    # them. Its mangled qualname carries the defining cell,
                    # as pickling by reference did.
                    fingerprint += primitive_to_bytes(obj.__qualname__)
                return (bytes, (type_sign(fingerprint, "function"),))
            try:
                if not is_primitive(obj) and is_data_primitive(obj):
                    h = hashlib.new(hash_type, usedforsecurity=False)
                    header, buffer = data_frames(obj)
                    h.update(header)
                    h.update(buffer)
                    return (bytes, (h.digest(),))
            except Exception:
                pass
            # Falls back to parent pickle
            return NotImplemented

    buf = io.BytesIO()
    _ContentHashPickler(buf).dump(obj)
    return buf.getvalue()
