"""Tests for marimo._mcp.server.responses module."""

from typing import TypedDict

import pytest

# Skip all MCP tests if Python < 3.10 or MCP not available
pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from marimo._mcp.server.responses import (
    SuccessResult,
    make_tool_success_result,
)


class SampleData(TypedDict):
    message: str
    count: int


def test_make_tool_success_result_basic():
    """Test basic success result creation."""
    data = {"message": "hello", "count": 42}

    result = make_tool_success_result(data)

    assert result["status"] == "success"
    assert result["data"] == data
    assert result["auth_required"] is False
    assert result["next_steps"] is None
    assert result["action_url"] is None
    assert result["message"] is None
    assert result["meta"] is None


def test_make_tool_success_result_with_all_params():
    """Test success result with all optional parameters."""
    data = {"message": "test", "count": 1}
    next_steps = ["Step 1", "Step 2"]

    result = make_tool_success_result(
        data=data,
        status="warning",
        auth_required=True,
        next_steps=next_steps,
        action_url="https://example.com",
        message="Custom message",
        meta={"key": "value"},
    )

    assert result["status"] == "warning"
    assert result["data"] == data
    assert result["auth_required"] is True
    assert result["next_steps"] == next_steps
    assert result["action_url"] == "https://example.com"
    assert result["message"] == "Custom message"
    assert result["meta"] == {"key": "value"}


def test_make_tool_success_result_typed_data():
    """Test success result with TypedDict data."""
    data: SampleData = {"message": "typed", "count": 100}

    result = make_tool_success_result(data)

    assert result["data"]["message"] == "typed"
    assert result["data"]["count"] == 100


def test_success_result_type_structure():
    """Test that SuccessResult has the expected structure."""
    # This is more of a type checking test
    data = {"test": "value"}
    result: SuccessResult[dict] = make_tool_success_result(data)

    # Verify all required fields exist
    assert "status" in result
    assert "data" in result
    assert "auth_required" in result
    assert "next_steps" in result
    assert "action_url" in result
    assert "message" in result
    assert "meta" in result
