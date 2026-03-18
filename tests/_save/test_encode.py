# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import pickle

import numpy as np

from marimo._save.encode import deterministic_dumps


class _ArrayWithSet:
    """Array-like whose pickle is non-deterministic across processes.

    The ``_tags`` set has hash-randomized iteration order across Python
    processes (PYTHONHASHSEED), so ``pickle.dumps`` produces different bytes
    on each run. But since this class has ``__array__``, ``_ContentHashPickler``
    replaces it with a deterministic content hash of the array data, discarding
    the non-deterministic set entirely.
    """

    def __init__(self, data: np.ndarray, tags: set) -> None:
        self._data = np.asarray(data, dtype=np.float32)
        self._tags = tags  # set — non-deterministic pickle order

    def __array__(self, dtype=None):  # type: ignore[override]
        return np.asarray(self._data, dtype=dtype)


def test_reducer_fires_replaces_with_content_hash() -> None:
    """reducer_override must replace data primitives, not pass through to pickle."""
    arr = np.arange(10, dtype=np.float32)
    obj = _ArrayWithSet(arr, tags={"a", "b", "c"})

    raw = pickle.dumps(obj)
    det = deterministic_dumps(obj, "sha256")

    # Reducer replaced the object — output must differ from raw pickle
    assert raw != det


def test_deterministic_for_same_data_different_set() -> None:
    """Two objects with same array data but different set attrs must hash the same.

    This mirrors the cross-process case: PYTHONHASHSEED changes set iteration
    order, so ``pickle.dumps`` differs between processes. ``deterministic_dumps``
    must not — it is content-addressed on the array data only.
    """
    arr = np.arange(10, dtype=np.float32)

    obj1 = _ArrayWithSet(arr, tags={"x", "y", "z"})
    obj2 = _ArrayWithSet(arr, tags={"p", "q", "r"})  # different set, same data

    # Raw pickle differs (different set content → different bytes)
    assert pickle.dumps(obj1) != pickle.dumps(obj2)

    # deterministic_dumps is content-addressed on the array only
    assert deterministic_dumps(obj1, "sha256") == deterministic_dumps(
        obj2, "sha256"
    )


def test_different_array_data_produces_different_hash() -> None:
    """Different array data must produce different deterministic hashes."""
    obj1 = _ArrayWithSet(np.zeros(10, dtype=np.float32), tags={"a"})
    obj2 = _ArrayWithSet(np.ones(10, dtype=np.float32), tags={"a"})

    assert deterministic_dumps(obj1, "sha256") != deterministic_dumps(
        obj2, "sha256"
    )


def test_plain_objects_pass_through() -> None:
    """Objects without data primitives should pickle normally."""
    obj = {"key": "value", "n": 42, "nested": [1, 2, 3]}
    assert deterministic_dumps(obj, "sha256") == pickle.dumps(obj)


def test_nested_data_primitives_in_container() -> None:
    """Data primitives nested in dicts/lists must still be replaced."""
    a = np.arange(5, dtype=np.float32)
    b = np.arange(5, dtype=np.float32)

    obj1 = {"arr": a, "label": "test"}
    obj2 = {"arr": b, "label": "test"}

    det1 = deterministic_dumps(obj1, "sha256")
    det2 = deterministic_dumps(obj2, "sha256")
    assert det1 == det2


def test_0d_array() -> None:
    """Scalar (0-d) arrays are a special code path in _contiguous_tensor_bytes."""
    obj = _ArrayWithSet(np.float32(3.14), tags={"x"})
    det1 = deterministic_dumps(obj, "sha256")
    det2 = deterministic_dumps(obj, "sha256")
    assert det1 == det2


def test_non_contiguous_array() -> None:
    """Non-contiguous arrays (e.g. strided, F-order) must serialize without error."""
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)
    f_arr = np.asfortranarray(arr)
    strided = arr[::2, ::2]

    # All layouts produce stable, non-crashing output
    for a in (arr, f_arr, strided):
        obj = _ArrayWithSet(a, tags=set())
        d1 = deterministic_dumps(obj, "sha256")
        d2 = deterministic_dumps(obj, "sha256")
        assert d1 == d2
