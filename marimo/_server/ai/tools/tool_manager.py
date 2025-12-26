# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from starlette.applications import (
    Starlette,  # noqa: TCH002 - required at runtime
)

from marimo import _loggers
from marimo._ai._tools.base import ToolBase, ToolContext
from marimo._ai._tools.tools_registry import SUPPORTED_BACKEND_AND_MCP_TOOLS
from marimo._config.config import CopilotMode
from marimo._server.ai.mcp.client import get_mcp_client
from marimo._server.ai.tools.types import (
    FunctionArgs,
    ToolCallResult,
    ToolDefinition,
    ToolSource,
    ValidationFunction,
)
from marimo._utils.once import once

if TYPE_CHECKING:
    from mcp.types import (  # type: ignore[import-not-found]
        CallToolResult,
        Tool as MCPRawTool,
    )

LOGGER = _loggers.marimo_logger()


class ToolManager:
    """Centralized manager for backend and frontend tools, with dynamic MCP tool access."""

    def __init__(self, app: Starlette) -> None:
        """Initialize the tool manager."""
        self._tools: dict[str, ToolDefinition] = {}
        self._backend_handlers: dict[str, Callable[[FunctionArgs], Any]] = {}
        self._validation_functions: dict[str, ValidationFunction] = {}
        self.app: Starlette = app

    @once
    def _init_backend_tools(self) -> None:
        """Initialize backend tools. We lazily register tools here instead of in the constructor for performance"""
        context = ToolContext(app=self.app)

        for tool in SUPPORTED_BACKEND_AND_MCP_TOOLS:
            tool_with_context = tool(context)
            self._register_backend_tool(tool_with_context)

    def _register_backend_tool(self, tool: ToolBase[Any, Any]) -> None:
        """Register a backend tool with its handler function and optional validator."""
        name = tool.name
        tool_definition, validation_function = tool.as_backend_tool(
            # TODO: Tools should define their own supported modes
            mode=["ask", "agent"]
        )
        self._tools[name] = tool_definition
        self._backend_handlers[name] = tool.__call__
        self._validation_functions[name] = validation_function

        LOGGER.debug(f"Registered backend tool: {name}")

    def _get_all_tools(self) -> list[ToolDefinition]:
        """Get all available backend, and MCP tools."""
        self._init_backend_tools()

        backend_tools = list(self._tools.values())
        mcp_tools = self._list_mcp_tools()
        all_tools = backend_tools + mcp_tools
        return all_tools

    def get_tools_for_mode(self, mode: CopilotMode) -> list[ToolDefinition]:
        """Get all tools available for a specific mode.

        Args:
            mode: The mode to get tools for.

        Returns:
            A list of tool definitions available for the given mode.
        """
        all_tools = self._get_all_tools()
        return [tool for tool in all_tools if mode in tool.mode]

    def _get_tool(
        self, name: str, source: Optional[ToolSource] = None
    ) -> Optional[ToolDefinition]:
        """Get tool definition by name."""

        if source:
            if source == "backend":
                # Check if it's a backend tool
                tool = self._tools.get(name)
                if tool and tool.source == "backend":
                    return tool
            elif source == "frontend":
                # ToolManager does not handle frontend tools
                LOGGER.warning(
                    f"Tool {name} is a frontend tool and should not be accessed in the backend."
                )
                return None
            elif source == "mcp":
                # Check MCP tools
                mcp_tools = self._list_mcp_tools()
                for mcp_tool in mcp_tools:
                    if mcp_tool.name == name:
                        return mcp_tool
            return None
        else:
            # No source specified, check all sources
            all_tools = self._get_all_tools()
            for tool in all_tools:
                if tool.name == name:
                    return tool
            return None

    def _validate_backend_tool_arguments(
        self, tool_name: str, arguments: FunctionArgs
    ) -> tuple[bool, str]:
        """Validate tool arguments using tool-specific or basic validation."""
        tool = self._get_tool(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"

        validator = self._validation_functions.get(tool_name)
        if validator:
            try:
                result = validator(arguments)
                if result is not None:
                    is_valid, error_message = result
                    if not is_valid:
                        LOGGER.warning(
                            f"Tool-specific validation failed for '{tool_name}': {error_message}"
                        )
                    return is_valid, error_message
            except Exception as e:
                error_msg = f"Error in tool-specific validation for '{tool_name}': {str(e)}"
                LOGGER.error(error_msg)
                return False, error_msg

        # If no validation, use basic validation against parameters schema
        required_params = tool.parameters.get("required", [])
        for param in required_params:
            if param not in arguments:
                error_msg = f"Missing required parameter '{param}'"
                LOGGER.warning(
                    f"Basic validation failed for '{tool_name}': {error_msg}"
                )
                return False, error_msg

        return True, ""

    def _list_mcp_tools(self) -> list[ToolDefinition]:
        """Get all MCP tools from the MCP client."""
        try:
            mcp_client = get_mcp_client()
            mcp_tools = mcp_client.get_all_tools()
            return [self._convert_mcp_tool(tool) for tool in mcp_tools]

        except Exception as e:
            LOGGER.error(f"Failed to get MCP tools: {str(e)}")
            return []

    def _convert_mcp_tool(self, mcp_tool: MCPRawTool) -> ToolDefinition:
        """Convert an MCP tool to marimo Tool format."""
        # Get namespaced name from meta field (meta is dict[str, Any] | None)
        meta = mcp_tool.meta or {}
        namespaced_name = (
            meta.get("namespaced_name") if isinstance(meta, dict) else None
        )

        # Convert to marimo Tool format
        return ToolDefinition(
            name=namespaced_name or mcp_tool.name,
            description=mcp_tool.description or "No description available",
            parameters=mcp_tool.inputSchema,
            source="mcp",
            # MCP tools available in ask mode and agent mode
            # TODO: Determine which tools to support in agent mode
            mode=["ask", "agent"],
        )

    async def invoke_tool(
        self, tool_name: str, arguments: FunctionArgs
    ) -> ToolCallResult:
        """Invoke a tool by name and return the result.

        Args:
            tool_name: The name of the tool to invoke.
            arguments: The arguments to pass to the tool.

        Returns:
            A ToolCallResult containing the result of the tool invocation.
        """
        self._init_backend_tools()

        tool = self._get_tool(tool_name)

        if not tool:
            return ToolCallResult(
                tool_name=tool_name,
                result=None,
                error=f"Internal error: Tool '{tool_name}' not found.",
            )

        if tool.source == "frontend":
            system_error = f"Frontend tool '{tool_name}' cannot be invoked in the backend. Frontend tools must be executed in the client."
            LOGGER.error(system_error)
            return ToolCallResult(
                tool_name=tool_name,
                result=None,
                error=f"Internal error: Tool '{tool_name}' is a frontend tool and cannot be executed on the server.",
            )

        try:
            if tool.source == "backend":
                # Handle backend tools
                is_valid, validation_error = (
                    self._validate_backend_tool_arguments(tool_name, arguments)
                )
                if not is_valid:
                    return ToolCallResult(
                        tool_name=tool_name,
                        result=None,
                        error=f"Invalid arguments for tool '{tool_name}': {validation_error}",
                    )
                handler = self._backend_handlers.get(tool_name)
                if not handler:
                    system_error = (
                        f"No handler found for backend tool '{tool_name}'."
                    )
                    LOGGER.error(system_error)
                    return ToolCallResult(
                        tool_name=tool_name,
                        result=None,
                        error=f"Internal error: Tool '{tool_name}' cannot be invoked.",
                    )
                result = await self._call_handler(handler, arguments)
                return ToolCallResult(
                    tool_name=tool_name, result=result, error=None
                )

            elif tool.source == "mcp":
                # Handle MCP tools
                call_result = await self._invoke_mcp_tool(tool_name, arguments)

                # Check if the result indicates an error using the MCP client
                mcp_client = get_mcp_client()

                if mcp_client.is_error_result(call_result):
                    # Extract error message from the result content
                    error_messages = mcp_client.extract_text_content(
                        call_result
                    )
                    error_text = (
                        " ".join(error_messages)
                        if error_messages
                        else "Unknown MCP tool error"
                    )
                    LOGGER.error(
                        f"MCP tool '{tool_name}' returned error: {error_text}"
                    )
                    return ToolCallResult(
                        tool_name=tool_name, result=None, error=error_text
                    )

                # For successful results, extract text content from CallToolResult
                success_messages = mcp_client.extract_text_content(call_result)
                result_text = (
                    " ".join(success_messages)
                    if success_messages
                    else "MCP tool completed successfully with no text output"
                )
                return ToolCallResult(
                    tool_name=tool_name, result=result_text, error=None
                )

            else:
                # Unknown tool source
                system_error = f"Unknown tool source: {tool.source} for tool {tool_name}. Supported sources are: backend and mcp."
                LOGGER.error(system_error)
                return ToolCallResult(
                    tool_name=tool_name,
                    result=None,
                    error=f"Internal error: Tool configuration error for tool {tool_name}.",
                )

        except Exception as e:
            error_message = f"Error invoking tool '{tool_name}': {str(e)}"
            LOGGER.error(error_message)
            return ToolCallResult(
                tool_name=tool_name, result=None, error=str(error_message)
            )

    async def _call_handler(
        self,
        handler: Callable[[FunctionArgs], Any],
        arguments: FunctionArgs,
    ) -> Any:
        """Call a tool handler, handling both sync and async functions."""
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(handler):
            return await handler(arguments)
        else:
            # Run sync function in thread pool to avoid blocking
            return await asyncio.get_event_loop().run_in_executor(
                None, handler, arguments
            )

    async def _invoke_mcp_tool(
        self, tool_name: str, arguments: FunctionArgs
    ) -> CallToolResult:
        """Invoke an MCP tool via the MCP client."""
        mcp_client = get_mcp_client()

        # Create properly typed parameters for the MCP tool
        params = mcp_client.create_tool_params(tool_name, arguments)

        # Invoke the tool
        call_result = await mcp_client.invoke_tool(tool_name, params)

        # Return the CallToolResult directly - let invoke_tool handle error checking
        return call_result


# Global tool manager instance
_TOOL_MANAGER: Optional[ToolManager] = None


def setup_tool_manager(app: Starlette) -> None:
    """Setup the tool manager with the app."""
    global _TOOL_MANAGER
    if _TOOL_MANAGER is None:
        _TOOL_MANAGER = ToolManager(app)
        LOGGER.info("ToolManager initialized")


def get_tool_manager() -> ToolManager:
    """Get the global tool manager instance."""
    if _TOOL_MANAGER is None:
        raise ValueError("ToolManager not initialized")
    return _TOOL_MANAGER
