from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette

from marimo._ai._tools.tools_registry import SUPPORTED_BACKEND_AND_MCP_TOOLS
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.mcp.client import MCPClient
from marimo._server.ai.tools.tool_manager import ToolManager
from marimo._server.ai.tools.types import (
    ToolCallResult,
    ToolDefinition,
)
from tests._server.mocks import get_starlette_server_state_init


@pytest.fixture
def manager():
    app = Starlette()
    get_starlette_server_state_init().apply(app.state)
    manager = ToolManager(app)
    assert len(manager._tools) == 0  # lazy init
    return manager


def test_get_tools_for_mode(manager: ToolManager):
    """Test getting tools filtered by mode."""

    # Mock the config to disable MCP
    tools = manager.get_tools_for_mode("ask")

    # Should have backend tools
    assert len(tools) == len(SUPPORTED_BACKEND_AND_MCP_TOOLS)

    # All should be backend tools for ask mode
    for tool in tools:
        assert tool.source == "backend"
        assert "ask" in tool.mode


async def test_invoke_tool_backend_success(manager: ToolManager):
    """Test successful backend tool invocation."""

    # Mock the config to disable MCP
    result = await manager.invoke_tool("get_active_notebooks", {})

    assert isinstance(result, ToolCallResult)
    assert result.tool_name == "get_active_notebooks"
    assert result.error is None
    assert result.result is not None


async def test_invoke_tool_not_found(manager: ToolManager):
    """Test invoking non-existent tool."""

    result = await manager.invoke_tool("nonexistent_tool", {})

    assert result.tool_name == "nonexistent_tool"
    assert result.result is None
    assert "not found" in result.error or result.error is None


async def test_invoke_tool_invalid_arguments(manager: ToolManager):
    """Test invoking tool with invalid arguments."""

    # Try to invoke with missing required arguments
    result = await manager.invoke_tool("get_cell_runtime_data", {})

    assert result.tool_name == "get_cell_runtime_data"
    assert result.result is None
    assert "Invalid arguments" in result.error or result.error is None


@pytest.mark.skipif(
    not DependencyManager.mcp.has(), reason="MCP SDK not available"
)
async def test_invoke_mcp_tool_preserves_structured_error(
    manager: ToolManager,
):
    from mcp.types import CallToolResult

    tool = ToolDefinition(
        name="mcp_server_tool",
        description="Tool",
        parameters={"type": "object"},
        source="mcp",
        mode=["ask"],
    )
    call_result = CallToolResult(
        is_error=True,
        content=[],
        structured_content={"reason": "denied", "code": 403},
    )

    with (
        patch.object(manager, "_get_tool", return_value=tool),
        patch.object(
            manager,
            "_invoke_mcp_tool",
            new=AsyncMock(return_value=call_result),
        ),
        patch(
            "marimo._server.ai.tools.tool_manager.get_mcp_client",
            return_value=MCPClient(),
        ),
    ):
        result = await manager.invoke_tool(tool.name, {})

    assert result.result is None
    assert result.error == '{"code": 403, "reason": "denied"}'


def test_validate_backend_tool_arguments(manager: ToolManager):
    """Test argument validation for backend tools."""

    # Test valid arguments
    is_valid, error = manager._validate_backend_tool_arguments(
        "get_cell_runtime_data",
        {"session_id": "test", "cell_ids": ["cell1"]},
    )
    assert is_valid is True
    assert error == ""

    # Test invalid argument (unknown key)
    is_valid, error = manager._validate_backend_tool_arguments(
        "get_cell_runtime_data",
        {"session_id": "test", "bad_key": "value"},
    )
    assert is_valid is False
    assert "Invalid arguments" in error


def test_get_tool(manager: ToolManager):
    """Test getting tool by name."""

    manager._init_backend_tools()
    tools = manager.get_tools_for_mode("ask")
    assert len(tools) > 0

    # Get backend tool
    tool = manager._get_tool("get_active_notebooks", source="backend")
    assert tool is not None
    assert tool.name == "get_active_notebooks"
    assert tool.source == "backend"

    # Get non-existent tool
    tool = manager._get_tool("nonexistent", source="backend")
    assert tool is None


def test_backend_tools_validation(manager: ToolManager):
    """Test validation for backend tools."""
    tools = manager._get_all_tools()
    assert len(tools) > 0

    backend_tools = [tool for tool in tools if tool.source == "backend"]
    assert len(backend_tools) > 0

    for tool in backend_tools:
        assert tool.name
        assert tool.description
        assert tool.parameters
        assert tool.source
        assert tool.mode

        # Validation of none
        is_valid, error = manager._validation_functions[tool.name](
            {"invalid": "argument"}
        )
        assert is_valid is False, error
