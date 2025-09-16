from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

import pytest

from marimo._ai._tools.base import ToolBase, ToolContext
from marimo._ai._tools.utils.exceptions import ToolExecutionError


@dataclass
class _Args:
    value: int


@dataclass
class _Out:
    doubled: int


class _EchoTool(ToolBase[_Args, _Out]):
    """Dummy tool for testing base adapter behavior."""

    def handle(self, args: _Args) -> _Out:
        return _Out(doubled=args.value * 2)


class _ErrorTool(ToolBase[_Args, _Out]):
    """Tool that raises errors for testing."""

    def handle(self, args: _Args) -> _Out:
        if args.value < 0:
            raise ToolExecutionError(
                "Negative values not allowed", code="NEGATIVE_VALUE"
            )
        if args.value == 0:
            raise ValueError("Zero is not allowed")
        return _Out(doubled=args.value * 2)


def test_as_mcp_tool_fn_returns_async_callable() -> None:
    tool = _EchoTool(ToolContext())
    handler = tool.as_mcp_tool_fn()

    assert inspect.iscoroutinefunction(handler)


def test_handler_annotations_and_signature() -> None:
    tool = _EchoTool(ToolContext())
    handler = tool.as_mcp_tool_fn()

    annotations: dict[str, Any] = getattr(handler, "__annotations__", {})
    assert annotations.get("args") is _Args
    assert annotations.get("return") is _Out

    sig = getattr(handler, "__signature__", None)
    assert sig is not None
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "args"
    assert sig.return_annotation is _Out


def test_name_and_description_defaults() -> None:
    tool = _EchoTool(ToolContext())
    # Name should default from class name
    assert tool.name == "_echo_tool"
    # Description defaults to class docstring (stripped)
    assert "Dummy tool" in (tool.description or "")


async def test_tool_call_with_valid_args() -> None:
    """Test __call__ method with valid arguments."""
    tool = _EchoTool(ToolContext())
    result = await tool(_Args(value=5))
    assert result.doubled == 10


async def test_tool_call_handles_tool_execution_error() -> None:
    """Test __call__ properly propagates ToolExecutionError."""
    tool = _ErrorTool(ToolContext())
    with pytest.raises(ToolExecutionError) as exc_info:
        await tool(_Args(value=-1))
    assert exc_info.value.code == "NEGATIVE_VALUE"


async def test_tool_call_wraps_unexpected_error() -> None:
    """Test __call__ wraps unexpected errors in ToolExecutionError."""
    tool = _ErrorTool(ToolContext())
    with pytest.raises(ToolExecutionError) as exc_info:
        await tool(_Args(value=0))
    assert exc_info.value.code == "UNEXPECTED_ERROR"


def test_tool_execution_error_basic() -> None:
    """Test basic ToolExecutionError functionality."""
    error = ToolExecutionError("Test error", code="TEST_CODE")
    assert error.message == "Test error"
    assert error.code == "TEST_CODE"
    assert error.is_retryable is False

    # Test structured message is JSON
    import json

    json.loads(str(error))  # Should not raise


def test_as_backend_tool() -> None:
    """Test as_backend_tool method."""
    tool = _EchoTool(ToolContext())
    definition, validator = tool.as_backend_tool(["ask"])

    assert definition.name == "_echo_tool"
    assert definition.source == "backend"
    assert definition.mode == ["ask"]

    # Test validator with valid args
    is_valid, msg = validator({"value": 42})
    assert is_valid is True
    assert msg == ""

    # Test validator with invalid args
    is_valid, msg = validator({"invalid": "field"})
    assert is_valid is False
    assert "Invalid arguments" in msg
