from __future__ import annotations

import os
from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.variables import get_variable_preview
from tests._data.mocks import create_dataframes


def test_get_variable_preview() -> None:
    # Test with various types
    # Test None
    assert get_variable_preview(None) == "None"

    # Test basic types
    assert get_variable_preview(42) == "42"
    assert get_variable_preview(3.14) == "3.14"

    # Test strings
    assert get_variable_preview("Hello, world!") == "'Hello, world!'"
    assert get_variable_preview("A" * 1000).startswith("'AAAAA")
    assert len(get_variable_preview("A" * 1000)) <= 52

    # Test sequences
    assert (
        get_variable_preview([1, 2, 3, 4, 5, 6, 7, 8]) == "[1, 2, ..., 7, 8]"
    )
    assert (
        get_variable_preview((1, "two", 3.0, [4, 5]))
        == "(1, 'two', 3.0, [4, 5])"
    )
    assert (
        get_variable_preview({1, 2, 3, 4, 5, 6, 7, 8}) == "{1, 2, ..., 7, 8}"
    )

    # Test dict
    assert (
        get_variable_preview({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})
        == "{'a': 1, 'b': 2, ..., 'e': 5, 'f': 6}"
    )

    # Test bytes/bytearray
    bytearray_preview = get_variable_preview(bytearray(b"Hello" * 1000))
    assert bytearray_preview.startswith("bytearray<5000 bytes:")

    bytes_preview = get_variable_preview(bytes([x % 256 for x in range(1000)]))
    assert bytes_preview.startswith("bytes<1000 bytes:")

    # Test other types
    assert get_variable_preview(range(100)).startswith("range(0, 100)")
    assert get_variable_preview(Exception("test error")).startswith(
        "<Exception object at"
    )

    # Test nested structures
    assert (
        get_variable_preview([[1, 2], [3, 4], [5, 6]])
        == "[[1, 2], [3, 4], [5, 6]]"
    )
    assert (
        get_variable_preview({"a": [1, 2], "b": {"c": 3}})
        == "{'a': [1, 2], 'b': {'c': 3}}"
    )

    # Test empty containers
    assert get_variable_preview([]) == "[]"
    assert get_variable_preview({}) == "{}"
    assert get_variable_preview(set()) == "{}"
    assert get_variable_preview(tuple()) == "()"

    # Test single-element containers
    assert get_variable_preview([1]) == "[1]"
    assert get_variable_preview({1}) == "{1}"
    assert get_variable_preview((1,)) == "(1)"

    # Test special strings
    assert get_variable_preview("\n\t\r") == "'\n\t\r'"
    assert get_variable_preview("🐍🚀") == "'🐍🚀'"
    assert get_variable_preview("'quoted'") == "''quoted''"

    # Test numeric types
    assert get_variable_preview(float("inf")) == "inf"
    assert get_variable_preview(float("-inf")) == "-inf"
    assert get_variable_preview(float("nan")) == "nan"
    assert get_variable_preview(complex(1, 2)) == "(1+2j)"
    assert get_variable_preview(1234567890123456789) == "1234567890123456789"

    # Test custom objects
    class CustomClass:
        def __str__(self):
            return "CustomStr"

        def __repr__(self):
            return "CustomRepr"

    assert get_variable_preview(CustomClass()).startswith(
        "<CustomClass object at"
    )

    # Test iterables
    from itertools import count, cycle, repeat

    assert get_variable_preview(count()).startswith("count(0)")
    assert get_variable_preview(cycle([1, 2])).startswith(
        "<itertools.cycle object at"
    )
    assert get_variable_preview(repeat(1)).startswith("repeat(1)")

    # Test file objects
    from io import BytesIO, StringIO

    assert get_variable_preview(StringIO("test")).startswith(
        "<StringIO object at"
    )
    assert get_variable_preview(BytesIO(b"test")).startswith(
        "<BytesIO object at"
    )

    # Test more complex nested structures
    complex_dict = {
        "a": [1, 2, 3],
        "b": {"c": [4, 5, 6], "d": (7, 8, 9)},
        "e": {1, 2, 3},
        "f": range(10),
    }
    assert (
        get_variable_preview(complex_dict)
        == """{'a': [1, ..., 3], 'b': {'c': [..., 4, 5, 6], 'd': (..., 7, 8, 9)}, 'e': {1, ..., 3}, 'f': range(0, 10)}"""
    )

    # Test deeply nested structures
    deep_nest = [[[[1]]]]
    assert get_variable_preview(deep_nest) == "[[[[..., 1]]]]"

    # Test mixed type sequences
    mixed = [1, "two", 3.0, [4, 5], {6, 7}, {"eight": 9}, (10,)]
    assert get_variable_preview(mixed) == (
        "[1, 'two', ..., {'eight': 9}, (10)]"
    )

    # Recursive dict
    inner_dict: dict[str, Any] = {"a": 1, "b": 2}
    inner_dict["c"] = inner_dict
    assert get_variable_preview(inner_dict) == (
        "{'a': 1, 'b': 2, 'c': <circular reference: dict>}"
    )


@pytest.mark.skipif(
    not DependencyManager.numpy.has(),
    reason="Numpy is not installed",
)
def test_get_variable_preview_memory_numpy() -> None:
    # Test memory usage with large array
    import numpy as np
    import psutil

    process = psutil.Process(os.getpid())

    # Create 100MB array
    large_array = np.ones(100 * 1024 * 1024 // 8, dtype=np.float64)

    mem_before = process.memory_info().rss
    preview = get_variable_preview(large_array)
    mem_after = process.memory_info().rss

    mem_diff_mb = (mem_after - mem_before) / (1024 * 1024)

    # Memory shouldn't increase significantly during preview
    assert mem_diff_mb < 1, (
        f"Memory increased by {mem_diff_mb}MB during preview"
    )
    assert preview == "[1. 1. 1. ... 1. 1. 1.]"


def test_get_variable_preview_bytesarray() -> None:
    import psutil

    process = psutil.Process(os.getpid())

    # Create 100MB bytesarray
    large_array = bytearray(b"A" * 100 * 1024 * 1024)

    mem_before = process.memory_info().rss
    preview = get_variable_preview(large_array)
    mem_after = process.memory_info().rss

    mem_diff_mb = (mem_after - mem_before) / (1024 * 1024)

    # Memory shouldn't increase significantly during preview
    assert mem_diff_mb < 1, (
        f"Memory increased by {mem_diff_mb}MB during preview"
    )
    assert (
        preview
        == "bytearray<104857600 bytes: 41414141414141414141414141414141...41414141414141414141414141414141>"
    )


@pytest.mark.parametrize(
    "df",
    create_dataframes({"A": list(range(1000000)), "B": ["x"] * 1000000}),
)
def test_get_variable_preview_dataframe(df: Any) -> None:
    import psutil

    process = psutil.Process(os.getpid())

    mem_before = process.memory_info().rss
    preview = get_variable_preview(df)
    mem_after = process.memory_info().rss

    mem_diff_mb = (mem_after - mem_before) / (1024 * 1024)

    assert mem_diff_mb < 10, (
        f"Memory increased by {mem_diff_mb}MB during preview"
    )
    assert "2 columns" in preview
