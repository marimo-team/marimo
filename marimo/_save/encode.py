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


def type_sign(value: bytes, label: str) -> bytes:
    # Appending all strings with a key disambiguates it from other types. e.g.
    # when the string value is the same as a float pack, or is the literal
    # ":none". If our content strings take the form: integrity + delimiter then
    # these types of collisions become very hard.
    #
    # Note that this does not fully protect against cache poisoning, as an
    # attacker can override python internals to provide a matched hash. A key
    # signed cache result is the only way to properly protect against this.
    #
    # Additionally, (less meaningful, but still possible)- a byte collision can
    # be manufactured by choosing data so long that the length of the data acts
    # as the data injection.
    #
    # TODO: Benchmark something like `sha1 (integrity) + delimiter`, this
    # method is chosen because it was assumed to be fast, but might be slow
    # with a copy of large data.
    length = struct.pack("!Q", len(value))
    return b"".join([value, length, bytes(":" + label, "utf-8")])


def iterable_sign(value: Iterable[Any], label: str) -> bytes:
    values = list(value)
    length = struct.pack("!Q", len(values))
    return b"".join([b"".join(values), length, bytes(":" + label, "utf-8")])


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
    return type_sign(_contiguous_tensor_bytes(data), "data")


def primitive_to_bytes(value: Any) -> bytes:
    if value is None:
        return b":none"
    if isinstance(value, str):
        return type_sign(bytes(f"{value}", "utf-8"), "str")
    if isinstance(value, float):
        return type_sign(struct.pack("d", value), "float")
    if isinstance(value, int):
        return type_sign(struct.pack("q", value), "int")
    if isinstance(value, tuple):
        return iterable_sign(map(primitive_to_bytes, value), "tuple")
    return type_sign(bytes(value), "bytes")


def common_container_to_bytes(value: Any) -> bytes:
    visited: dict[int, int] = {}

    def recurse_container(value: Any) -> bytes:
        if id(value) in visited:
            return type_sign(bytes(visited[id(value)]), "id")
        if isinstance(value, dict):
            visited[id(value)] = len(visited)
            return iterable_sign(
                map(recurse_container, sorted(value.items())), "dict"
            )
        if isinstance(value, list):
            visited[id(value)] = len(visited)
            return iterable_sign(map(recurse_container, value), "list")
        if isinstance(value, set):
            visited[id(value)] = len(visited)
            return iterable_sign(map(recurse_container, sorted(value)), "set")
        # Tuple may be only data primitive, not fully primitive.
        if isinstance(value, tuple):
            return iterable_sign(map(recurse_container, value), "tuple")

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
    """``pickle.dumps`` replacement that produces more deterministic bytes."""
    from marimo._save.stubs import maybe_get_custom_stub

    class _ContentHashPickler(pickle.Pickler):
        def reducer_override(self, obj: Any) -> Any:
            if stub := maybe_get_custom_stub(obj):
                return (bytes, (stub.to_bytes(),))
            try:
                if not is_primitive(obj) and is_data_primitive(obj):
                    h = hashlib.new(hash_type, usedforsecurity=False)
                    h.update(_contiguous_tensor_bytes(obj))
                    return (bytes, (h.digest(),))
            except Exception:
                pass
            # Falls back to parent pickle
            return NotImplemented

    buf = io.BytesIO()
    _ContentHashPickler(buf).dump(obj)
    return buf.getvalue()
