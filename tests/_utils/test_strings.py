# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.platform import is_windows
from marimo._utils.strings import (
    _mslex_quote,
    _quote_for_cmd,
    _wrap_in_quotes,
    cmd_quote,
    standardize_annotation_quotes,
)


class TestCmdQuote:
    """Test the cmd_quote function for cross-platform command line quoting."""

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    def test_posix_simple_string(self):
        """Test simple strings on POSIX systems."""
        assert cmd_quote("hello") == "hello"
        assert cmd_quote("path/to/file") == "path/to/file"

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    def test_posix_strings_with_spaces(self):
        """Test strings with spaces on POSIX systems."""
        assert cmd_quote("hello world") == "'hello world'"
        assert cmd_quote("path with spaces") == "'path with spaces'"

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    def test_posix_strings_with_special_chars(self):
        """Test strings with special characters on POSIX systems."""
        assert cmd_quote("hello'world") == "'hello'\"'\"'world'"
        assert cmd_quote('hello"world') == "'hello\"world'"
        assert cmd_quote("hello$world") == "'hello$world'"

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific test")
    def test_windows_simple_string(self):
        """Test simple strings on Windows."""
        assert cmd_quote("hello") == "hello"
        assert cmd_quote("path\\to\\file") == "path\\to\\file"

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific test")
    def test_windows_empty_string(self):
        """Test empty string on Windows."""
        assert cmd_quote("") == '""'

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific test")
    def test_windows_strings_with_spaces(self):
        """Test strings with spaces on Windows."""
        assert cmd_quote("hello world") == '"hello world"'
        assert (
            cmd_quote("C:\\Program Files\\app") == '"C:\\Program Files\\app"'
        )

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific test")
    def test_windows_strings_with_special_chars(self):
        """Test strings with Windows special characters."""
        # Test % character
        assert cmd_quote("hello%world") == "hello^%world"
        # Test ! character
        assert cmd_quote("hello!world") == "hello^!world"
        # Test with quotes
        assert cmd_quote('hello"world') == 'hello\\^"world'


class TestWrapInQuotes:
    """Test the _wrap_in_quotes helper function."""

    def test_simple_string(self):
        """Test wrapping simple strings."""
        assert _wrap_in_quotes("hello") == '"hello"'
        assert _wrap_in_quotes("world") == '"world"'

    def test_string_with_trailing_backslash(self):
        """Test strings with trailing backslashes."""
        assert _wrap_in_quotes("path\\") == '"path\\\\"'
        assert _wrap_in_quotes("path\\\\") == '"path\\\\\\\\"'

    def test_string_without_trailing_backslash(self):
        """Test strings without trailing backslashes."""
        assert _wrap_in_quotes("path\\file") == '"path\\file"'
        assert _wrap_in_quotes("no\\backslash") == '"no\\backslash"'

    def test_empty_string(self):
        """Test empty string."""
        assert _wrap_in_quotes("") == '""'


class TestQuoteForCmd:
    """Test the _quote_for_cmd helper function."""

    def test_simple_string(self):
        """Test quoting simple strings."""
        assert _quote_for_cmd("hello") == "hello"

    def test_string_with_percent(self):
        """Test strings with % character."""
        assert _quote_for_cmd("hello%world") == "hello^%world"

    def test_string_with_exclamation(self):
        """Test strings with ! character."""
        assert _quote_for_cmd("hello!world") == "hello^!world"

    def test_string_with_quotes(self):
        """Test strings with quote characters."""
        assert _quote_for_cmd('hello"world') == 'hello\\^"world'

    def test_string_with_spaces(self):
        """Test strings requiring quoting due to spaces."""
        result = _quote_for_cmd("hello world")
        assert result == '"hello world"'

    def test_complex_string(self):
        """Test complex strings with multiple special characters."""
        result = _quote_for_cmd("hello%!world")
        assert result == "hello^%^!world"


class TestMslexQuote:
    """Test the _mslex_quote function."""

    def test_empty_string(self):
        """Test empty string returns double quotes."""
        assert _mslex_quote("") == '""'

    def test_simple_string(self):
        """Test simple strings that don't need quoting."""
        assert _mslex_quote("hello") == "hello"
        assert _mslex_quote("path\\to\\file") == "path\\to\\file"

    def test_string_with_spaces(self):
        """Test strings with spaces."""
        assert _mslex_quote("hello world") == '"hello world"'

    def test_string_with_special_chars(self):
        """Test strings with Windows cmd special characters."""
        assert _mslex_quote("hello%world") == "hello^%world"
        assert _mslex_quote("hello!world") == "hello^!world"

    def test_string_with_quotes(self):
        """Test strings with quote characters."""
        result = _mslex_quote('hello"world')
        assert '"' in result  # Should be quoted
        assert "\\" in result  # Should have escaping

    def test_optimization_shorter_alt(self):
        """Test that shorter alternative quoting is used when available."""
        # This tests the optimization where a shorter alternative is preferred
        result = _mslex_quote("x!")
        assert result == "x^!"  # Shorter than "x\\"^!""


class TestStandardizeAnnotationQuotes:
    """Test the standardize_annotation_quotes function."""

    def test_no_quotes(self):
        """Test annotations without quotes."""
        assert standardize_annotation_quotes("int") == "int"
        assert standardize_annotation_quotes("List[str]") == "List[str]"

    def test_single_quotes_to_double(self):
        """Test converting single quotes to double quotes."""
        assert (
            standardize_annotation_quotes("Literal['foo']") == 'Literal["foo"]'
        )
        assert (
            standardize_annotation_quotes("Literal['foo', 'bar']")
            == 'Literal["foo", "bar"]'
        )

    def test_already_double_quotes(self):
        """Test that double quotes are preserved."""
        assert (
            standardize_annotation_quotes('Literal["foo"]') == 'Literal["foo"]'
        )
        assert (
            standardize_annotation_quotes('Literal["foo", "bar"]')
            == 'Literal["foo", "bar"]'
        )

    def test_mixed_quotes_with_internal_double_quotes(self):
        """Test that single quotes are preserved when they contain unescaped double quotes."""
        # This should preserve single quotes due to internal double quotes
        result = standardize_annotation_quotes("Literal['say \"hello\"']")
        assert result == "Literal['say \"hello\"']"

    def test_escaped_quotes_in_single_quotes(self):
        """Test handling of escaped quotes within single-quoted strings."""
        result = standardize_annotation_quotes("Literal['it\\'s']")
        assert result == 'Literal["it\'s"]'

    def test_complex_annotation(self):
        """Test complex type annotations."""
        input_annotation = "Union[Literal['foo', 'bar'], Optional['baz']]"
        expected = 'Union[Literal["foo", "bar"], Optional["baz"]]'
        assert standardize_annotation_quotes(input_annotation) == expected

    def test_nested_quotes(self):
        """Test nested quote scenarios."""
        # Test escaped double quotes in single-quoted strings
        result = standardize_annotation_quotes("Literal['test\\\"value']")
        assert result == 'Literal["test\\\\"value"]'

    def test_empty_string_literal(self):
        """Test empty string literals."""
        assert standardize_annotation_quotes("Literal['']") == 'Literal[""]'
        assert standardize_annotation_quotes('Literal[""]') == 'Literal[""]'

    def test_multiple_string_literals(self):
        """Test multiple string literals in one annotation."""
        input_annotation = (
            "Dict[Literal['key1', 'key2'], Literal['val1', 'val2']]"
        )
        expected = 'Dict[Literal["key1", "key2"], Literal["val1", "val2"]]'
        assert standardize_annotation_quotes(input_annotation) == expected
