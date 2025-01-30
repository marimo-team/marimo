from __future__ import annotations

import pytest

from marimo._output.hypertext import Html
from marimo._plugins.stateless.sidebar import sidebar


def test_sidebar_string():
    """Test sidebar with string input."""
    result = sidebar("test content")
    assert isinstance(result, Html)
    assert "width" not in result._text


def test_sidebar_list():
    """Test sidebar with list input."""
    result = sidebar(["item1", "item2"])
    assert isinstance(result, Html)
    assert "width" not in result._text


def test_sidebar_with_footer():
    """Test sidebar with footer."""
    result = sidebar("content", footer="footer text")
    assert isinstance(result, Html)
    assert "width" not in result._text


def test_sidebar_list_both_width_and_footer():
    """Test sidebar with both width and footer."""
    result = sidebar(["item1", "item2"], footer=["footer1", "footer2"])
    assert isinstance(result, Html)
    assert "width" not in result._text


def test_sidebar_with_width():
    """Test sidebar with custom width."""
    result = sidebar("content", width="300px")
    assert isinstance(result, Html)
    assert "data-width='&quot;300px&quot;'" in result._text


def test_sidebar_unsupported_methods():
    """Test that unsupported methods raise TypeError."""
    s = sidebar("content")
    with pytest.raises(TypeError):
        s.batch()
    with pytest.raises(TypeError):
        s.center()
    with pytest.raises(TypeError):
        s.right()
    with pytest.raises(TypeError):
        s.left()
    with pytest.raises(TypeError):
        s.callout()
    with pytest.raises(TypeError):
        s.style()
