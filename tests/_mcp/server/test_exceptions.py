"""Tests for marimo._mcp.server.exceptions module."""

import json

import pytest

# Skip all MCP tests if Python < 3.10 or MCP not available
pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from marimo._mcp.server.exceptions import ToolExecutionError


def test_tool_execution_error_basic():
    """Test basic ToolExecutionError creation."""
    error = ToolExecutionError("Something went wrong")

    assert error.original_message == "Something went wrong"
    assert error.code == "TOOL_ERROR"
    assert error.status == 400
    assert error.is_retryable is False
    assert error.suggested_fix is None
    assert error.meta == {}


def test_tool_execution_error_with_all_params():
    """Test ToolExecutionError with all parameters."""
    meta_data = {"session_id": "test123", "cell_id": "abc"}

    error = ToolExecutionError(
        "Custom error message",
        code="CUSTOM_ERROR",
        status=500,
        is_retryable=True,
        suggested_fix="Try restarting the server",
        meta=meta_data,
    )

    assert error.original_message == "Custom error message"
    assert error.code == "CUSTOM_ERROR"
    assert error.status == 500
    assert error.is_retryable is True
    assert error.suggested_fix == "Try restarting the server"
    assert error.meta == meta_data


def test_tool_execution_error_structured_message():
    """Test that the structured message contains all error details."""
    error = ToolExecutionError(
        "Test error",
        code="TEST_CODE",
        status=422,
        is_retryable=True,
        suggested_fix="Fix the test",
        meta={"key": "value"},
    )

    # The structured message should be valid JSON
    structured_msg = str(error)
    parsed = json.loads(structured_msg)

    assert parsed["message"] == "Test error"
    assert parsed["code"] == "TEST_CODE"
    assert parsed["status"] == 422
    assert parsed["is_retryable"] is True
    assert parsed["suggested_fix"] == "Fix the test"
    assert parsed["meta"] == {"key": "value"}


def test_tool_execution_error_to_dict():
    """Test the to_dict method."""
    error = ToolExecutionError(
        "Dict test",
        code="DICT_ERROR",
        status=404,
        is_retryable=False,
        suggested_fix="Check the ID",
        meta={"test": True},
    )

    error_dict = error.to_dict()

    expected = {
        "code": "DICT_ERROR",
        "message": "Dict test",
        "status": 404,
        "is_retryable": False,
        "suggested_fix": "Check the ID",
        "meta": {"test": True},
    }

    assert error_dict == expected


def test_tool_execution_error_inheritance():
    """Test that ToolExecutionError properly inherits from Exception."""
    error = ToolExecutionError("Test inheritance")

    assert isinstance(error, Exception)

    # Should be raisable and catchable
    with pytest.raises(ToolExecutionError) as exc_info:
        raise error

    assert exc_info.value.original_message == "Test inheritance"


def test_tool_execution_error_none_meta():
    """Test that None meta gets converted to empty dict."""
    error = ToolExecutionError("Test", meta=None)

    assert error.meta == {}
