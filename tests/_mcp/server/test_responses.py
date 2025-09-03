"""Tests for marimo._mcp.server.responses module."""

from typing import TypedDict

import pytest

# Skip all MCP tests if Python < 3.10 or MCP not available
pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from marimo._mcp.server.responses import (
    SuccessResult,
)


class SampleData(TypedDict):
    message: str
    count: int


def test_success_result_basic():
    """Test basic success result creation."""
    result = SuccessResult()

    assert result.status == "success"
    assert result.auth_required is False
    assert result.next_steps is None
    assert result.action_url is None
    assert result.message is None
    assert result.meta is None


def test_success_result_with_all_params():
    """Test success result with all optional parameters."""
    next_steps = ["Step 1", "Step 2"]

    result = SuccessResult(
        status="warning",
        auth_required=True,
        next_steps=next_steps,
        action_url="https://example.com",
        message="Custom message",
        meta={"key": "value"},
    )

    assert result.status == "warning"
    assert result.auth_required is True
    assert result.next_steps == next_steps
    assert result.action_url == "https://example.com"
    assert result.message == "Custom message"
    assert result.meta == {"key": "value"}


def test_success_result_with_meta():
    """Test success result with meta data."""
    meta_data = {"key": "value", "count": 100}

    result = SuccessResult(meta=meta_data)

    assert result.meta == meta_data


def test_success_result_type_structure():
    """Test that SuccessResult has the expected structure."""
    result = SuccessResult()

    # Verify all required fields exist
    assert hasattr(result, "status")
    assert hasattr(result, "auth_required")
    assert hasattr(result, "next_steps")
    assert hasattr(result, "action_url")
    assert hasattr(result, "message")
    assert hasattr(result, "meta")
