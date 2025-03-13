from __future__ import annotations

from marimo._utils.repr import format_repr


def test_format_repr_with_simple_values() -> None:
    """Test format_repr with basic value types."""

    class TestClass:
        pass

    obj = TestClass()
    items = {"a": 1, "b": "hello", "c": True}

    result = format_repr(obj, items)

    assert result == "TestClass(a=1, b=hello, c=True)"


def test_format_repr_with_empty_items() -> None:
    """Test format_repr with an empty items dict."""

    class TestClass:
        pass

    obj = TestClass()
    result = format_repr(obj, {})

    assert result == "TestClass()"


def test_format_repr_with_none_values() -> None:
    """Test format_repr with None values."""

    class TestClass:
        pass

    obj = TestClass()
    items = {"a": None, "b": "hello"}
    result = format_repr(obj, items)

    assert result == "TestClass(a=None, b=hello)"
