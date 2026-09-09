# Copyright 2026 Marimo. All rights reserved.
"""Deterministic encoding of Python values to bytes for content-addressed hashing.

This module owns the conversion of Python objects (primitives, tensors,
containers, arbitrary picklable objects) into canonical byte sequences.
"""

from __future__ import annotations

import hashlib
import io
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
    tag = label.encode("utf-8")
    # len(memoryview) counts the first dimension, not the number of bytes.
    size = value.nbytes if isinstance(value, memoryview) else len(value)
    return b"".join(
        [struct.pack("!Q", len(tag)), tag, struct.pack("!Q", size), value]
    )


def iterable_sign(value: Iterable[Any], label: str) -> bytes:
    # An item count alone cannot distinguish different partitions of the bytes.
    return type_sign(
        b"".join(type_sign(item, "item") for item in value), label
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


def data_to_buffer(data: Tensor) -> bytes:
    array = standardize_tensor(data)
    metadata = primitive_to_bytes(
        (
            type(data).__module__,
            type(data).__qualname__,
            array.dtype,
            array.shape,
            array.strides,
        )
    )
    return type_sign(metadata, "array") + type_sign(
        _contiguous_tensor_bytes(array), "data"
    )


def primitive_to_bytes(value: Any) -> bytes:
    if value is None:
        return type_sign(b"", "none")
    if value is Ellipsis:
        return type_sign(b"", "ellipsis")
    if type(value) is bool:
        return type_sign(bytes([value]), "bool")
    if type(value) is str:
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
    # Pickle preserves numeric subclasses without allocating bytes(np.int64(n)).
    return type_sign(pickle.dumps(value, protocol=4), "pickle")


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
        return data_to_buffer(value)

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


def deterministic_dumps(obj: Any, hash_type: str) -> bytes:
    """`pickle.dumps` replacement that produces more deterministic bytes."""
    from marimo._save.stubs import maybe_get_custom_stub

    class _ContentHashPickler(pickle.Pickler):
        def reducer_override(self, obj: Any) -> Any:
            if stub := maybe_get_custom_stub(obj):
                return (bytes, (stub.to_bytes(),))
            try:
                if not is_primitive(obj) and is_data_primitive(obj):
                    h = hashlib.new(hash_type, usedforsecurity=False)
                    h.update(data_to_buffer(obj))
                    return (bytes, (h.digest(),))
            except Exception:
                pass
            # Falls back to parent pickle
            return NotImplemented

    buf = io.BytesIO()
    _ContentHashPickler(buf).dump(obj)
    return buf.getvalue()
