from __future__ import annotations

from unittest.mock import Mock, patch

from marimo._runtime.context import (
    ContextNotInitializedError,
)
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.script_context import ScriptRuntimeContext
from marimo._runtime.context.utils import get_mode


def test_get_mode_kernel_run():
    """Test get_mode() returns 'run' when in kernel run mode"""
    mock_context = Mock(spec=KernelRuntimeContext)
    mock_context.session_mode = "run"

    with patch(
        "marimo._runtime.context.utils.get_context", return_value=mock_context
    ):
        assert get_mode() == "run"


def test_get_mode_kernel_edit():
    """Test get_mode() returns 'edit' when in kernel edit mode"""
    mock_context = Mock(spec=KernelRuntimeContext)
    mock_context.session_mode = "edit"

    with patch(
        "marimo._runtime.context.utils.get_context", return_value=mock_context
    ):
        assert get_mode() == "edit"


def test_get_mode_script():
    """Test get_mode() returns 'script' when in script context"""
    mock_context = Mock(spec=ScriptRuntimeContext)

    with patch(
        "marimo._runtime.context.utils.get_context", return_value=mock_context
    ):
        assert get_mode() == "script"


def test_get_mode_no_context():
    """Test get_mode() returns None when context is not initialized"""
    with patch(
        "marimo._runtime.context.utils.get_context",
        side_effect=ContextNotInitializedError,
    ):
        assert get_mode() is None
