from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.ipython_formatters import (
    IPythonFormatter,
    ReprMimeBundle,
)
from marimo._output.formatting import get_formatter

HAS_DEPS = DependencyManager.ipython.has()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_register_html_display():
    from IPython.display import HTML

    IPythonFormatter().register()

    # Test HTML with direct content
    html = HTML("<div>Hello World</div>")
    formatter = get_formatter(html)
    assert formatter is not None
    result = formatter(html)
    assert result == ("text/html", "<div>Hello World</div>")


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.append")
def test_display_patch(mock_append: MagicMock):
    from IPython.display import HTML, display

    unpatch = IPythonFormatter().register()
    try:
        # Test regular display
        obj = HTML("<div>Test</div>")
        display(obj)
        mock_append.assert_called_once_with(obj)
        mock_append.reset_mock()

        # Test raw mimebundle display
        mimebundle = {"text/html": "<div>Raw Test</div>"}
        display(mimebundle, raw=True)
        mock_append.assert_called_once()
        assert isinstance(mock_append.call_args[0][0], ReprMimeBundle)
        assert mock_append.call_args[0][0].data == mimebundle
    finally:
        unpatch()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
def test_repr_mimebundle():
    data = {"text/html": "<div>Test</div>", "text/plain": "Test"}
    bundle = ReprMimeBundle(data)
    assert bundle._repr_mimebundle_() == data
    # Test that include/exclude params are ignored
    assert bundle._repr_mimebundle_(include=["text/html"]) == data


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.append")
def test_display_html(mock_append: MagicMock):
    from IPython.display import display_html

    unpatch = IPythonFormatter().register()

    try:
        display_html("<div>Test</div>", raw=True)
        mock_append.assert_called_once()
        assert isinstance(mock_append.call_args[0][0], ReprMimeBundle)
        assert mock_append.call_args[0][0].data == {
            "text/html": "<div>Test</div>"
        }
    finally:
        unpatch()
