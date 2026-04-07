# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import array
import pickle
from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.encode import deterministic_dumps

HAS_PANDAS = DependencyManager.pandas.has()
HAS_NUMPY = DependencyManager.numpy.has()


class _ArrayWithSet:
    """Array-like whose pickle is non-deterministic across processes.

    The ``_tags`` set has hash-randomized iteration order across Python
    processes (PYTHONHASHSEED), so ``pickle.dumps`` produces different bytes
    on each run. But since this class has ``__array__``, ``_ContentHashPickler``
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
    order, so ``pickle.dumps`` differs between processes. ``deterministic_dumps``
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
    assert deterministic_dumps(obj, "sha256") == pickle.dumps(obj)


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
