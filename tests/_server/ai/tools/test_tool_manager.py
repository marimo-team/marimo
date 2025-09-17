from __future__ import annotations

import pytest
from starlette.applications import Starlette

from marimo._ai._tools.tools_registry import SUPPORTED_BACKEND_AND_MCP_TOOLS
from marimo._config.manager import get_default_config_manager
from marimo._server.ai.tools.tool_manager import ToolManager
from marimo._server.ai.tools.types import ToolCallResult
from tests._server.mocks import get_mock_session_manager


@pytest.fixture
def manager():
    app = Starlette()
    app.state.config_manager = get_default_config_manager(current_path=None)
    app.state.session_manager = get_mock_session_manager()
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


def test_validate_backend_tool_arguments(manager: ToolManager):
    """Test argument validation for backend tools."""

    # Test valid arguments
    is_valid, error = manager._validate_backend_tool_arguments(
        "get_cell_runtime_data", {"session_id": "test", "cell_id": "cell1"}
    )
    assert is_valid is True
    assert error == ""

    # Test missing required argument
    is_valid, error = manager._validate_backend_tool_arguments(
        "get_cell_runtime_data",
        {"session_id": "test"},  # missing cell_id
    )
    assert is_valid is False
    assert "missing 1 required positional argument: 'cell_id'" in error


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
