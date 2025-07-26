# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.stateless.plain_text import plain_text


def test_plain_text_basic() -> None:
    """Test basic plain_text functionality."""
    result = plain_text("Hello, World!")
    assert "Hello, World!" in result.text
    assert "<pre" in result.text
    assert "</pre>" in result.text


def test_plain_text_html_escaping() -> None:
    """Test that plain_text properly escapes HTML characters."""
    # Test the reported bug case
    result = plain_text("<x")
    assert "&lt;x" in result.text
    assert "<x" not in result.text or result.text.count("<x") == 0

    # Test other HTML characters
    result = plain_text("</script>")
    assert "&lt;/script&gt;" in result.text

    result = plain_text("<div>content</div>")
    assert "&lt;div&gt;content&lt;/div&gt;" in result.text

    result = plain_text("&amp;")
    assert "&amp;amp;" in result.text


def test_plain_text_preserves_whitespace() -> None:
    """Test that plain_text preserves spaces and newlines."""
    text_with_spaces = "line 1\n  line 2 with spaces\nline 3"
    result = plain_text(text_with_spaces)
    # The text should contain the original spacing
    assert "line 1" in result.text
    assert "  line 2 with spaces" in result.text
    assert "line 3" in result.text


def test_plain_text_empty_string() -> None:
    """Test plain_text with empty string."""
    result = plain_text("")
    assert result.text == "<pre style='font-size: 12px'></pre>"
