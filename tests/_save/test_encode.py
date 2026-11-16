# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import array
import enum
import os
import pickle
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.encode import (
    attempt_signed_bytes,
    common_container_to_bytes,
    data_to_buffer,
    deterministic_dumps,
    primitive_to_bytes,
)

HAS_PANDAS = DependencyManager.pandas.has()
HAS_NUMPY = DependencyManager.numpy.has()


class _ArrayWithSet:
    """Array-like whose pickle is non-deterministic across processes.

    The `_tags` set has hash-randomized iteration order across Python
    processes (PYTHONHASHSEED), so `pickle.dumps` produces different bytes
    on each run. But since this class has `__array__`, `_ContentHashPickler`
    replaces it with a deterministic content hash of the array data, discarding
    the non-deterministic set entirely.
    """

    def __init__(self, data: list[float], tags: set) -> None:
        self._data = array.array("f", data)
        self._tags = tags

    def __array__(self, dtype: Any = None) -> Any:
        import numpy as np

        return np.frombuffer(self._data, dtype=np.float32)


def test_reducer_fires_replaces_with_content_hash() -> None:
    """reducer_override must replace data primitives, not pass through to pickle."""
    obj = _ArrayWithSet([1.0, 2.0, 3.0], tags={"a", "b", "c"})

    raw = pickle.dumps(obj)
    det = deterministic_dumps(obj, "sha256")

    assert raw != det


def test_deterministic_for_same_data_different_set() -> None:
    """Two objects with same array data but different set attrs must hash the same.

    This mirrors the cross-process case: PYTHONHASHSEED changes set iteration
    order, so `pickle.dumps` differs between processes. `deterministic_dumps`
    must not — it is content-addressed on the array data only.
    """
    data = list(range(10))

    obj1 = _ArrayWithSet(data, tags={"x", "y", "z"})
    obj2 = _ArrayWithSet(data, tags={"p", "q", "r"})

    assert pickle.dumps(obj1) != pickle.dumps(obj2)
    assert deterministic_dumps(obj1, "sha256") == deterministic_dumps(
        obj2, "sha256"
    )


def test_different_array_data_produces_different_hash() -> None:
    """Different array data must produce different deterministic hashes."""
    obj1 = _ArrayWithSet([0.0] * 10, tags={"a"})
    obj2 = _ArrayWithSet([1.0] * 10, tags={"a"})

    assert deterministic_dumps(obj1, "sha256") != deterministic_dumps(
        obj2, "sha256"
    )


def test_plain_objects_pass_through() -> None:
    """Objects without data primitives should pickle normally."""
    obj = {"key": "value", "n": 42, "nested": [1, 2, 3]}
    assert deterministic_dumps(obj, "sha256") == pickle.dumps(obj, protocol=4)


def test_0d_array() -> None:
    """Scalar (0-d) arrays are a special code path in _contiguous_tensor_bytes."""
    obj = _ArrayWithSet([3.14], tags={"x"})
    det1 = deterministic_dumps(obj, "sha256")
    det2 = deterministic_dumps(obj, "sha256")
    assert det1 == det2


@pytest.mark.skipif(
    not HAS_PANDAS or not HAS_NUMPY,
    reason="pandas and numpy are required",
)
def test_dataframe_with_integer_columns() -> None:
    """Regression: pd.DataFrame(np.random.randn(3, 3)) has integer column names.

    narwhals interprets df[0] as row selection, not column selection, causing
    AttributeError: 'DataFrame' object has no attribute 'dtype'.
    """
    import numpy as np
    import pandas as pd

    df = pd.DataFrame(np.random.randn(3, 3))
    # Must not raise
    result = deterministic_dumps(df, hash_type="sha256")
    assert isinstance(result, bytes)


@pytest.mark.skipif(
    not HAS_PANDAS or not HAS_NUMPY,
    reason="pandas and numpy are required",
)
def test_dataframe_same_data_same_hash() -> None:
    """Two DataFrames with identical data must produce the same hash."""
    import numpy as np
    import pandas as pd

    data = np.arange(9, dtype=float).reshape(3, 3)
    df1 = pd.DataFrame(data)
    df2 = pd.DataFrame(data.copy())

    assert deterministic_dumps(df1, hash_type="sha256") == deterministic_dumps(
        df2, hash_type="sha256"
    )


def test_bytearray_encodes_to_deterministic_bytes() -> None:
    """A bytearray encodes to deterministic bytes that vary by content."""
    a = common_container_to_bytes(bytearray(b"abc"))
    assert type(a) is bytes
    assert a == common_container_to_bytes(bytearray(b"abc"))
    assert a != common_container_to_bytes(bytearray(b"xyz"))


def test_bytearray_does_not_collide_with_equal_bytes() -> None:
    """bytearray and bytes of equal content sign under distinct labels."""
    assert common_container_to_bytes(bytearray(b"abc")) != (
        common_container_to_bytes(b"abc")
    )


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="polars required"
)
def test_polars_numeric_hash_depends_on_values() -> None:
    import polars as pl

    frame = pl.DataFrame({"x": [1, 2], "y": [3, 4]})
    encoded = data_to_buffer(frame)
    assert encoded == data_to_buffer(frame.rename({"x": "renamed"}))
    assert encoded != data_to_buffer(pl.DataFrame({"x": [1, 2], "y": [3, 5]}))


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="polars required"
)
@pytest.mark.parametrize("as_frame", [False, True])
def test_polars_non_numeric_state_uses_fallback(as_frame: bool) -> None:
    import polars as pl

    series = pl.Series("label", ["a", "b"])
    data = (
        series.to_frame().with_columns(count=pl.Series([1, 2]))
        if as_frame
        else series
    )
    value = {"data": data}
    assert attempt_signed_bytes(value, "state") is value


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="polars required"
)
@pytest.mark.parametrize("as_frame", [False, True])
def test_polars_non_numeric_pickle_fallback_preserves_values(
    as_frame: bool,
) -> None:
    import polars as pl

    series = pl.Series("label", ["a", "b"])
    value = series.to_frame() if as_frame else series
    assert pickle.loads(deterministic_dumps(value, "sha256")).equals(value)


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="polars required"
)
@pytest.mark.parametrize("as_frame", [False, True])
@pytest.mark.parametrize("in_container", [False, True])
def test_polars_object_hash_uses_fallback(
    as_frame: bool, in_container: bool
) -> None:
    import polars as pl

    series = pl.Series("objects", [object()], dtype=pl.Object)
    value: Any = series.to_frame() if as_frame else series
    value = {"data": value} if in_container else value

    assert attempt_signed_bytes(value, "state") is value


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
@pytest.mark.parametrize("change", ["dtype", "shape", "transpose"])
def test_pickled_array_preserves_metadata(change: str) -> None:
    import numpy as np

    before = np.arange(4, dtype=np.int64).reshape(2, 2)
    if change == "dtype":
        after = before.view(np.float64)
    elif change == "shape":
        after = before.reshape(2, 1, 2)
    else:
        after = before.T
    assert deterministic_dumps(before, "sha256") != deterministic_dumps(
        after, "sha256"
    )


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
def test_structured_dtype_with_overlapping_fields() -> None:
    import numpy as np

    overlapping = np.dtype(
        {"names": ["a", "b"], "formats": ["<i4", "<i4"], "offsets": [0, 2]}
    )
    with pytest.raises(ValueError):
        overlapping.descr  # noqa: B018
    value = np.zeros(3, dtype=overlapping)
    assert data_to_buffer(value) != data_to_buffer(value.view(np.uint8))


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
def test_numpy_scalar_keyed_by_dtype_and_value() -> None:
    import numpy as np

    assert primitive_to_bytes(np.int64(2)) != primitive_to_bytes(np.int64(3))
    assert primitive_to_bytes(np.int64(2)) != primitive_to_bytes(np.int32(2))
    assert primitive_to_bytes(np.int64(2)) != primitive_to_bytes(2)
    # bytes(np.int64(2)) is two zero bytes, which used to be the encoding.
    assert primitive_to_bytes(np.int64(2)) != primitive_to_bytes(bytes(2))


def test_number_subclass_keyed_by_type() -> None:
    class Celsius(float):
        pass

    class Level(enum.IntEnum):
        LOW = 1

    class Rounded(float):
        def __repr__(self) -> str:
            return f"{self:.1f}"

    assert primitive_to_bytes(Celsius(1.0)) != primitive_to_bytes(Celsius(2.0))
    assert primitive_to_bytes(Celsius(1.0)) != primitive_to_bytes(1.0)
    assert repr(Rounded(1.01)) == repr(Rounded(1.02))
    assert primitive_to_bytes(Rounded(1.01)) != primitive_to_bytes(
        Rounded(1.02)
    )
    assert primitive_to_bytes(Fraction(1, 3)) != primitive_to_bytes(
        Fraction(1, 4)
    )
    assert primitive_to_bytes(Decimal(1)) != primitive_to_bytes(1)
    # bytes(Level.LOW) is one zero byte, which would collide with bytes(1).
    assert primitive_to_bytes(Level.LOW) != primitive_to_bytes(bytes(1))
    assert primitive_to_bytes(Level.LOW) != primitive_to_bytes(1)


def test_non_number_falls_back_to_bytes() -> None:
    class Blob(bytes):
        pass

    class Color(str, enum.Enum):
        RED = "red"

    assert primitive_to_bytes(Blob(b"x")) == primitive_to_bytes(b"x")
    assert primitive_to_bytes(Color.RED) == primitive_to_bytes("red")


def test_equal_scalars_of_different_types_are_distinct() -> None:
    values = [1, 1.0, True, "1", b"1", 1 + 0j, None, (1,), 2**64, -1]
    encoded = [primitive_to_bytes(v) for v in values]
    assert len(set(encoded)) == len(values)
    assert primitive_to_bytes(0.0) != primitive_to_bytes(-0.0)


def test_item_boundaries_are_framed() -> None:
    assert primitive_to_bytes(("ab", "c")) != primitive_to_bytes(("a", "bc"))
    assert common_container_to_bytes(["ab", "c"]) != common_container_to_bytes(
        ["a", "bc"]
    )
    assert common_container_to_bytes([1, 23]) != common_container_to_bytes(
        [12, 3]
    )


def test_dict_order_is_observable() -> None:
    assert common_container_to_bytes({"a": 1, "b": 2}) != (
        common_container_to_bytes({"b": 2, "a": 1})
    )


def test_set_encoding_is_order_independent() -> None:
    # hash(2**61) == hash(1), so insertion order decides iteration order.
    assert list({1, 2**61}) != list({2**61, 1})
    assert common_container_to_bytes({1, 2**61}) == (
        common_container_to_bytes({2**61, 1})
    )
    # Mixed-type members cannot be sorted, so the encoded items are sorted.
    assert common_container_to_bytes({1, "a", (2,)}) == (
        common_container_to_bytes({(2,), "a", 1})
    )


def test_set_dumps_are_seed_independent() -> None:
    # Set iteration order follows PYTHONHASHSEED for str members. A value
    # pickled through deterministic_dumps must not.
    program = (
        "from marimo._save.encode import deterministic_dumps\n"
        "print(deterministic_dumps({'a', 'b', 'c', frozenset({'d', 'e'})},"
        " 'sha256').hex())"
    )
    digests = {
        subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        ).stdout.strip()
        for seed in ("0", "1", "42")
    }
    assert len(digests) == 1
