from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.ipython_formatters import (
    IPythonFormatter,
)

HAS_DEPS = DependencyManager.ipython.has()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.replace")
@patch("marimo._runtime.output._output.append")
def test_display_update(mock_append: MagicMock, mock_replace: MagicMock):
    """Test that display with display_id returns a handle and update works."""
    # Import IPython before patching to ensure we get the module
    import IPython.display

    # Apply our formatter patch
    unpatch = IPythonFormatter().register()

    try:
        # Now use the patched functions
        obj1 = IPython.display.HTML("<div>Initial Content</div>")
        handle = IPython.display.display(obj1, display_id="test-id")

        # Verify handle was returned and append was called
        assert handle is not None
        assert handle.display_id == "test-id"
        mock_append.assert_called_once_with(obj1)
        mock_append.reset_mock()

        # Test update_display
        obj2 = IPython.display.HTML("<div>Updated Content</div>")
        IPython.display.update_display(obj2, display_id="test-id")

        # Verify replace was called
        mock_replace.assert_called_once_with(obj2)

        # Test handle.update method
        mock_replace.reset_mock()

        obj3 = IPython.display.HTML("<div>Handle Updated Content</div>")
        handle.update(obj3)

        # Verify replace was called
        mock_replace.assert_called_once_with(obj3)

    finally:
        unpatch()


@pytest.mark.skipif(not HAS_DEPS, reason="IPython not installed")
@patch("marimo._runtime.output._output.append")
def test_display_auto_id(mock_append: MagicMock):
    """Test that display with display_id=True auto-generates an ID."""
    # Import IPython before patching
    import IPython.display

    # Apply our formatter patch
    unpatch = IPythonFormatter().register()

    try:
        # Test display with auto-generated display_id
        obj = IPython.display.HTML("<div>Auto ID Content</div>")
        handle = IPython.display.display(obj, display_id=True)

        # Verify handle was returned with a UUID
        assert handle is not None
        assert isinstance(handle.display_id, str)
        assert len(handle.display_id) > 0
        mock_append.assert_called_once_with(obj)

    finally:
        unpatch()
