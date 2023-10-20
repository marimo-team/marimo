# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, List

from marimo._plugins.ui._impl.table import (
    TableData,
    _get_row_headers,
    _normalize_data,
)
from marimo._runtime.conftest import MockedKernel
from marimo._runtime.runtime import ExecutionContext


def test_normalize_data() -> None:
    # Create kernel and give the execution context an existing cell
    mocked = MockedKernel()
    mocked.k.execution_context = ExecutionContext("test_cell_id", False)

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
    ]  # type: ignore
    result = _normalize_data(data)
    assert result == [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]

    # Test with pandas DataFrame
    try:
        import pandas as pd

        data = pd.DataFrame({"column1": [1, 2, 3], "column2": ["a", "b", "c"]})
        result = _normalize_data(data)
        assert isinstance(result, str)
        assert result.endswith(".csv")
    except ImportError:
        pass

    # Test with invalid data type
    data2: Any = "invalid data type"
    try:
        _normalize_data(data2)
    except ValueError as e:
        assert str(e) == "data must be a list or tuple."

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


def test_get_row_headers() -> None:
    try:
        import pandas as pd

        expected: List[tuple[str, List[str]]]

        # Test with pandas DataFrame
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        df.index.name = "Index"
        assert _get_row_headers(df) == []

        # Test with non-DataFrame input
        assert _get_row_headers([1, 2, 3]) == []

        # Test with MultiIndex
        arrays = [
            ["foo", "bar", "baz"],
            ["one", "two", "three"],
        ]
        df_multi = pd.DataFrame({"A": range(3)}, index=arrays)
        expected = [
            ("", ["foo", "bar", "baz"]),
            ("", ["one", "two", "three"]),
        ]
        assert _get_row_headers(df_multi) == expected

        # Test with RangeIndex
        df_range = pd.DataFrame({"A": range(3)})
        assert _get_row_headers(df_range) == []

        # Test with categorical Index
        df_cat = pd.DataFrame({"A": range(3)})
        df_cat.index = pd.CategoricalIndex(["a", "b", "c"])
        expected = [("", ["a", "b", "c"])]
        assert _get_row_headers(df_cat) == expected

        # Test with named categorical Index
        df_cat = pd.DataFrame({"A": range(3)})
        df_cat.index = pd.CategoricalIndex(["a", "b", "c"], name="Colors")
        expected = [("Colors", ["a", "b", "c"])]
        assert _get_row_headers(df_cat) == expected
    except ImportError:
        pass
