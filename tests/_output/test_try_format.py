from __future__ import annotations

from dataclasses import dataclass

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatting import (
    FormattedOutput,
    Plain,
    formatter,
    opinionated_formatter,
    try_format,
)


# Test class with _mime_ protocol
class MimeObject:
    def _mime_(self):
        return ("text/html", "<p>mime test</p>")


# Test class with _display_ protocol
class DisplayObject:
    def _display_(self):
        return MimeObject()


# Test class for basic formatting
@dataclass
class BasicObject:
    value: str


# Register a formatter for BasicObject
@formatter(BasicObject)
def format_basic(obj: BasicObject) -> tuple[KnownMimeType, str]:
    return ("text/html", f"<span>{obj.value}</span>")


# Test class for opinionated formatting
@dataclass
class OpinionatedObject:
    value: str


# Register an opinionated formatter
@opinionated_formatter(OpinionatedObject)
def format_opinionated(obj: OpinionatedObject) -> tuple[KnownMimeType, str]:
    return ("text/html", f"<div>{obj.value}</div>")


# Test class that raises error during formatting
@dataclass
class ErrorObject:
    value: str


@formatter(ErrorObject)
def format_error(_: ErrorObject) -> tuple[KnownMimeType, str]:
    raise ValueError("Formatting error")


def is_plain_text(output: FormattedOutput) -> bool:
    assert output.mimetype == "text/plain"
    assert output.traceback is None
    assert output.exception is None
    return True


def is_html(output: FormattedOutput) -> bool:
    assert output.mimetype == "text/html"
    assert output.traceback is None
    assert output.exception is None
    return True


def test_primitives():
    # 1 and "1" are different
    assert try_format(1).data == "<pre class='text-xs'>1</pre>"
    assert try_format("1").data == "<pre class='text-xs'>&#x27;1&#x27;</pre>"
    assert (
        try_format("hello").data
        == "<pre class='text-xs'>&#x27;hello&#x27;</pre>"
    )
    assert try_format("").data == "<pre class='text-xs'>&#x27;&#x27;</pre>"
    assert try_format(None).data == ""
    # True and 'True' are different
    assert try_format(True).data == "<pre class='text-xs'>True</pre>"
    assert (
        try_format("True").data
        == "<pre class='text-xs'>&#x27;True&#x27;</pre>"
    )
    assert try_format(False).data == "<pre class='text-xs'>False</pre>"
    assert try_format(1.0).data == "<pre class='text-xs'>1.0</pre>"
    assert try_format(1.0 + 1.0j).data == "<pre class='text-xs'>(1+1j)</pre>"
    assert try_format([1, 2, 3]).data == "[1, 2, 3]"
    assert try_format({"a": 1, "b": 2}).data == '{"a": 1, "b": 2}'
    assert (
        try_format(set([1, 2, 3])).data
        == "<pre class='text-xs'>{1, 2, 3}</pre>"
    )


def test_none_value():
    """Test formatting of None value."""
    result = try_format(None)
    assert is_plain_text(result)
    assert result.data == ""


def test_basic_formatter():
    """Test basic formatter registration and usage."""
    obj = BasicObject("test")
    result = try_format(obj)
    assert is_html(result)
    assert result.data == "<span>test</span>"


def test_mime_protocol():
    """Test object implementing _mime_ protocol."""
    obj = MimeObject()
    result = try_format(obj)
    assert is_html(result)
    assert result.data == "<p>mime test</p>"


def test_display_protocol():
    """Test object implementing _display_ protocol."""
    obj = DisplayObject()
    result = try_format(obj)
    assert is_html(result)
    assert result.data == "<p>mime test</p>"


def test_error_handling():
    """Test error handling during formatting."""
    obj = ErrorObject("test")
    result = try_format(obj)
    assert result.mimetype == "text/plain"
    assert result.data == ""
    assert result.traceback is not None
    assert isinstance(result.exception, ValueError)
    assert str(result.exception) == "Formatting error"


def test_plain_object():
    """Test Plain wrapper to opt out of opinionated formatting."""
    obj = Plain(OpinionatedObject("test"))
    result = try_format(obj)
    # Should fall back to string representation since we opted out of opinionated formatter
    assert is_html(result)
    assert result.data.startswith("<pre class='text-xs'>Plain(")


def test_opinionated_formatter():
    """Test opinionated formatter with and without include_opinionated flag."""
    obj = OpinionatedObject("test")

    # With opinionated formatting (default)
    result = try_format(obj)
    assert is_html(result)
    assert result.data == "<div>test</div>"

    # Without opinionated formatting
    result = try_format(obj, include_opinionated=False)
    assert is_html(result)
    assert "test" in result.data.lower()


def test_does_not_use_only_str_repr():
    """Test fallback to string representation for objects without formatters."""

    class NoFormatter:
        def __str__(self):
            return "no formatter"

    obj = NoFormatter()
    result = try_format(obj)
    assert is_html(result)
    assert result.data.startswith("<pre class='text-xs'>")
    assert "test_does_not_use_only_str_repr" in result.data.lower()


def test_str_vs_repr():
    """Test that str is preferred over repr."""

    class StrReprTest:
        def __str__(self):
            return "str_value"

        def __repr__(self):
            return "repr_value"

    obj = StrReprTest()
    result = try_format(obj)
    assert is_html(result)
    assert "str_value" not in result.data.lower()
    assert "repr_value" in result.data.lower()


def test_repr_fallback():
    """Test that repr is used when str not available."""

    class ReprOnlyTest:
        def __repr__(self):
            return "repr_value"

    obj = ReprOnlyTest()
    result = try_format(obj)
    assert is_html(result)
    assert "repr_value" in result.data.lower()


def test_repr_is_used_over_str():
    """Test that repr is used over str when both are available."""

    class StrErrorTest:
        def __str__(self):
            raise ValueError("str error")

        def __repr__(self):
            return "repr_value"

    obj = StrErrorTest()
    result = try_format(obj)
    assert is_html(result)
    assert result.data == "<pre class='text-xs'>repr_value</pre>"


@pytest.mark.skipif(
    not DependencyManager.numpy.has(), reason="numpy is not installed"
)
def test_numpy_array():
    """Test formatting of numpy array."""
    import numpy as np

    obj = np.array([1, 2, 3])
    result = try_format(obj)
    assert is_html(result)
    assert result.data == "<pre class='text-xs'>array([1, 2, 3])</pre>"
