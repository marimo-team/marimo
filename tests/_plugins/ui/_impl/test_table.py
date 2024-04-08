# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager
from marimo._plugins.ui._impl.utils.dataframe import TableData
from marimo._runtime.runtime import Kernel


def _normalize_data(data: Any) -> list[dict[str, Any]]:
    return DefaultTableManager._normalize_data(data)


def test_normalize_data(executing_kernel: Kernel) -> None:
    # unused, except for the side effect of giving the kernel an execution
    # context
    del executing_kernel

    # Create kernel and give the execution context an existing cell
    data: TableData

    # Test with list of integers
    data = [1, 2, 3]
    result = _normalize_data(data)
    assert result == [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ]

    # Test with list of strings
    data = ["a", "b", "c"]
    result = _normalize_data(data)
    assert result == [
        {"value": "a"},
        {"value": "b"},
        {"value": "c"},
    ]

    # Test with list of dictionaries
    data = [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]
    result = _normalize_data(data)
    assert result == [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]

    # Dictionary with list of integers
    data = {"key": [1, 2, 3]}
    result = _normalize_data(data)
    assert result == [
        {"key": 1},
        {"key": 2},
        {"key": 3},
    ]

    # Dictionary with tuple of integers
    data = {"key": (1, 2, 3)}
    result = _normalize_data(data)
    assert result == [
        {"key": 1},
        {"key": 2},
        {"key": 3},
    ]

    # Test with empty list
    data = []
    result = _normalize_data(data)
    assert result == []

    # Test with invalid data type
    data2: Any = "invalid data type"
    try:
        _normalize_data(data2)
    except ValueError as e:
        assert str(e) == "data must be a list or tuple or a dict of lists."

    # Test with invalid data structure
    data3: Any = [set([1, 2, 3])]
    try:
        _normalize_data(data3)
    except ValueError as e:
        assert (
            str(e)
            == "data must be a sequence of JSON-serializable types, or a "
            + "sequence of dicts."
        )
