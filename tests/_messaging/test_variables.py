from __future__ import annotations

import os
from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.variables import (
    _format_variable_value,
    _stringify_variable_value,
    create_variable_value,
    get_variable_preview,
)
from marimo._output.hypertext import Html
from marimo._plugins.ui._impl.input import slider
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


class TestStringifyVariableValue:
    """Test _stringify_variable_value function."""

    def test_short_string(self) -> None:
        result = _stringify_variable_value("hello")
        assert result == "hello"

    def test_long_string_truncated(self) -> None:
        long_str = "a" * 100
        result = _stringify_variable_value(long_str)
        assert len(result) == 50
        assert result == "a" * 50

    def test_integer(self) -> None:
        result = _stringify_variable_value(42)
        assert result == "42"

    def test_list(self) -> None:
        result = _stringify_variable_value([1, 2, 3])
        assert "[1, 2, 3]" in result

    def test_dict(self) -> None:
        result = _stringify_variable_value({"a": 1, "b": 2})
        assert "a" in result
        assert "1" in result

    def test_broken_str(self) -> None:
        """Test object that raises BaseException in __str__."""

        class Broken:
            def __str__(self) -> str:
                raise BaseException("boom")  # noqa: TRY002

        result = _stringify_variable_value(Broken())
        # get_variable_preview falls back to repr() which returns "<Broken object at ...>"
        assert result.startswith("<Broken object at")

    def test_none(self) -> None:
        result = _stringify_variable_value(None)
        assert result == "None"

    def test_float(self) -> None:
        result = _stringify_variable_value(3.14159)
        assert "3.14" in result

    def test_bool(self) -> None:
        assert _stringify_variable_value(True) == "True"
        assert _stringify_variable_value(False) == "False"

    def test_tuple(self) -> None:
        result = _stringify_variable_value((1, 2, 3))
        assert "(1, 2, 3)" in result


class TestFormatVariableValue:
    """Test _format_variable_value function."""

    def test_ui_element(self) -> None:
        """Test UIElement extracts .value attribute."""
        s = slider(1, 10, value=5)
        result = _format_variable_value(s)
        assert result == "5"

    def test_html(self) -> None:
        """Test Html extracts .text attribute."""
        h = Html("<span>hello</span>")
        result = _format_variable_value(h)
        # Html.text returns the raw HTML string
        assert result == h.text
        assert result == "<span>hello</span>"

    def test_module(self) -> None:
        """Test ModuleType extracts .__name__."""
        import sys

        result = _format_variable_value(sys)
        assert result == "sys"

    def test_regular_value(self) -> None:
        """Test regular value passes through to stringify."""
        result = _format_variable_value(42)
        assert result == "42"

    def test_string(self) -> None:
        """Test string value."""
        result = _format_variable_value("hello")
        assert result == "hello"


class TestCreateVariableValue:
    """Test create_variable_value function."""

    def test_integer(self) -> None:
        vv = create_variable_value("x", 42)
        assert vv.name == "x"
        assert vv.value == "42"
        assert vv.datatype == "int"

    def test_string(self) -> None:
        vv = create_variable_value("s", "hello")
        assert vv.name == "s"
        assert vv.value == "hello"
        assert vv.datatype == "str"

    def test_none(self) -> None:
        vv = create_variable_value("n", None)
        assert vv.name == "n"
        assert vv.value == "None"
        assert vv.datatype is None

    def test_list(self) -> None:
        vv = create_variable_value("lst", [1, 2, 3])
        assert vv.name == "lst"
        assert "[1, 2, 3]" in vv.value
        assert vv.datatype == "list"

    def test_ui_element(self) -> None:
        """Test UIElement value extraction."""
        s = slider(1, 10, value=7)
        vv = create_variable_value("slider", s)
        assert vv.name == "slider"
        assert vv.value == "7"
        assert vv.datatype == "slider"

    def test_html(self) -> None:
        """Test Html text extraction."""
        h = Html("<span>content</span>")
        vv = create_variable_value("html", h)
        assert vv.name == "html"
        # Html.text returns the raw HTML string
        assert vv.value == h.text
        assert vv.value == "<span>content</span>"
        assert vv.datatype == "Html"

    def test_module_type(self) -> None:
        """Test ModuleType name extraction."""
        import os

        vv = create_variable_value("os_module", os)
        assert vv.name == "os_module"
        assert vv.value == "os"
        assert vv.datatype == "module"

    def test_custom_datatype(self) -> None:
        """Test overriding datatype."""
        vv = create_variable_value("x", 42, datatype="custom_int")
        assert vv.name == "x"
        assert vv.value == "42"
        assert vv.datatype == "custom_int"

    def test_exception_in_type_name(self) -> None:
        """Test handling exception when getting type name."""

        class BrokenType:
            @property
            def __class__(self):
                raise Exception("boom")  # noqa: TRY002

        # type() builtin doesn't use the __class__ property, so this doesn't raise
        vv = create_variable_value("broken", BrokenType())
        assert vv.name == "broken"
        # type() still works and returns the actual type
        assert vv.datatype == "BrokenType"

    def test_exception_in_format(self) -> None:
        """Test handling exception during formatting."""

        class BrokenStr:
            def __str__(self) -> str:
                raise BaseException("boom")  # noqa: TRY002

        vv = create_variable_value("broken", BrokenStr())
        assert vv.name == "broken"
        # get_variable_preview falls back to repr() which returns "<BrokenStr object at ...>"
        assert vv.value.startswith("<BrokenStr object at")

    def test_long_string_truncation(self) -> None:
        """Test that long strings are truncated."""
        long_str = "x" * 100
        vv = create_variable_value("long", long_str)
        assert vv.name == "long"
        assert len(vv.value) == 50
        assert vv.value == "x" * 50
        assert vv.datatype == "str"

    def test_large_collection(self) -> None:
        """Test handling of large collections."""
        large_list = list(range(1000))
        vv = create_variable_value("big", large_list)
        assert vv.name == "big"
        # Should have preview with ellipsis
        assert "..." in vv.value
        assert vv.datatype == "list"

    def test_dict_value(self) -> None:
        """Test dictionary value."""
        vv = create_variable_value("d", {"a": 1, "b": 2})
        assert vv.name == "d"
        assert "a" in vv.value
        assert vv.datatype == "dict"

    def test_float_value(self) -> None:
        """Test float value."""
        vv = create_variable_value("pi", 3.14159)
        assert vv.name == "pi"
        assert "3.14" in vv.value
        assert vv.datatype == "float"

    def test_bool_values(self) -> None:
        """Test boolean values."""
        vv_true = create_variable_value("t", True)
        assert vv_true.name == "t"
        assert vv_true.value == "True"
        assert vv_true.datatype == "bool"

        vv_false = create_variable_value("f", False)
        assert vv_false.name == "f"
        assert vv_false.value == "False"
        assert vv_false.datatype == "bool"
