# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional

from marimo import _loggers
from marimo._config.config import CopilotMode

if TYPE_CHECKING:
    from mcp.types import (  # type: ignore[import-not-found]
        CallToolResult,
        Tool as MCPRawTool,
    )

LOGGER = _loggers.marimo_logger()

# Type aliases for tool system
FunctionArgs = dict[str, Any]
ValidationFunction = Callable[[FunctionArgs], tuple[bool, str]]

ToolSource = Literal["mcp", "backend", "frontend"]


@dataclass
class Tool:
    """Tool definition compatible with ai-sdk-ui format."""

    name: str
    description: str
    parameters: dict[str, Any]
    source: ToolSource
    mode: list[CopilotMode]  # tools can be available in multiple modes


@dataclass
class ToolResult:
    """Represents the result of a tool invocation."""

    tool_name: str
    result: Any
    error: Optional[str] = None


class ToolManager:
    """Centralized manager for backend and frontend tools, with dynamic MCP tool access."""

    def __init__(self) -> None:
        """Initialize the tool manager."""
        self._tools: dict[str, Tool] = {}
        self._backend_handlers: dict[str, Callable[[FunctionArgs], Any]] = {}
        self._validation_functions: dict[str, ValidationFunction] = {}

        # Don't register tools in __init__ to avoid circular imports
        # Tools will be registered when get_tool_manager() is first called
        LOGGER.info(
            "ToolManager created (tools will be registered on first access)"
        )

    def register_backend_tool(
        self,
        tool: Tool,
        handler: Callable[[FunctionArgs], Any],
        validator: Optional[ValidationFunction] = None,
    ) -> None:
        """Register a backend tool with its handler function and optional validator."""
        if tool.source != "backend":
            raise ValueError("Tool source must be 'backend'")

        self._tools[tool.name] = tool
        self._backend_handlers[tool.name] = handler
        if validator:
            self._validation_functions[tool.name] = validator
        LOGGER.debug(f"Registered backend tool: {tool.name}")

    def register_frontend_tool(self, tool: Tool) -> None:
        """Register a frontend tool (definition only - no handler or validator needed)."""
        if tool.source != "frontend":
            raise ValueError("Tool source must be 'frontend'")

        self._tools[tool.name] = tool
        LOGGER.debug(f"Registered frontend tool: {tool.name}")

    def get_all_tools(self) -> list[Tool]:
        """Get all available frontend, backend, and MCP tools."""
        local_tools = list(self._tools.values())
        mcp_tools = self.list_mcp_tools()
        all_tools = local_tools + mcp_tools
        return all_tools

    def get_tools_for_mode(self, mode: CopilotMode) -> list[Tool]:
        """Get all tools available for a specific mode."""
        all_tools = self.get_all_tools()
        return [tool for tool in all_tools if mode in tool.mode]

    def get_tool(
        self, name: str, source: Optional[ToolSource] = None
    ) -> Optional[Tool]:
        """Get tool definition by name."""
        if source:
            if source == "backend":
                # Check if it's a backend tool
                tool = self._tools.get(name)
                if tool and tool.source == "backend":
                    return tool
            elif source == "frontend":
                # Check if it's a frontend tool
                tool = self._tools.get(name)
                if tool and tool.source == "frontend":
                    return tool
            elif source == "mcp":
                # Check MCP tools
                mcp_tools = self.list_mcp_tools()
                for mcp_tool in mcp_tools:
                    if mcp_tool.name == name:
                        return mcp_tool
            return None
        else:
            # No source specified, check all sources
            all_tools = self.get_all_tools()
            for tool in all_tools:
                if tool.name == name:
                    return tool
            return None

    def validate_backend_tool_arguments(
        self, tool_name: str, arguments: FunctionArgs
    ) -> tuple[bool, str]:
        """Validate tool arguments using tool-specific validation function or fallback to basic validation."""
        tool = self.get_tool(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"

        # Use tool-specific validation function if available
        if tool_name in self._validation_functions:
            try:
                validator = self._validation_functions[tool_name]
                is_valid, error_message = validator(arguments)
                if not is_valid:
                    LOGGER.warning(
                        f"Tool-specific validation failed for '{tool_name}': {error_message}"
                    )
                return is_valid, error_message
            except Exception as e:
                error_msg = f"Error in tool-specific validation for '{tool_name}': {str(e)}"
                LOGGER.error(error_msg)
                return False, error_msg

        # Fallback to basic validation against parameters schema
        required_params = tool.parameters.get("required", [])

        # Check required parameters
        for param in required_params:
            if param not in arguments:
                error_msg = f"Missing required parameter '{param}'"
                LOGGER.warning(
                    f"Basic validation failed for '{tool_name}': {error_msg}"
                )
                return False, error_msg

        return True, ""

    def list_mcp_tools(self) -> list[Tool]:
        """Get all MCP tools from the MCP client."""
        try:
            from marimo._server.ai.mcp import get_mcp_client

            mcp_client = get_mcp_client()
            mcp_tools = mcp_client.get_all_tools()
            return [self.convert_mcp_tool(tool) for tool in mcp_tools]

        except Exception as e:
            LOGGER.error(f"Failed to get MCP tools: {str(e)}")
            return []

    def convert_mcp_tool(self, mcp_tool: MCPRawTool) -> Tool:
        """Convert an MCP tool to marimo Tool format."""
        # Get namespaced name from meta field (meta is dict[str, Any] | None)
        meta = mcp_tool.meta or {}
        namespaced_name = (
            meta.get("namespaced_name") if isinstance(meta, dict) else None
        )

        # Convert to marimo Tool format
        return Tool(
            name=namespaced_name or mcp_tool.name,
            description=mcp_tool.description or "No description available",
            parameters=mcp_tool.inputSchema,
            source="mcp",
            mode=["ask"],  # MCP tools available in ask mode for now
            # TODO(bjoaquinc): change default mode to "agent" when we add agent mode
        )

    async def invoke_tool(
        self, tool_name: str, arguments: FunctionArgs
    ) -> ToolResult:
        """Invoke a tool by name and return the result."""
        tool = self.get_tool(tool_name)

        if not tool:
            return ToolResult(
                tool_name=tool_name,
                result=None,
                error=f"Internal error: Tool '{tool_name}' not found.",
            )

        if tool.source == "frontend":
            system_error = f"Frontend tool '{tool_name}' cannot be invoked in the backend. Frontend tools must be executed in the client."
            LOGGER.error(system_error)
            return ToolResult(
                tool_name=tool_name,
                result=None,
                error=f"Internal error: Tool '{tool_name}' is a frontend tool and cannot be executed on the server.",
            )

        try:
            if tool.source == "backend":
                # Handle backend tools
                is_valid, validation_error = (
                    self.validate_backend_tool_arguments(tool_name, arguments)
                )
                if not is_valid:
                    return ToolResult(
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
                    return ToolResult(
                        tool_name=tool_name,
                        result=None,
                        error=f"Internal error: Tool '{tool_name}' cannot be invoked.",
                    )
                result = await self._call_handler(handler, arguments)
                return ToolResult(
                    tool_name=tool_name, result=result, error=None
                )

            elif tool.source == "mcp":
                # Handle MCP tools
                call_result = await self._invoke_mcp_tool(tool_name, arguments)

                # Check if the result indicates an error using the MCP client
                from marimo._server.ai.mcp import get_mcp_client

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
                    return ToolResult(
                        tool_name=tool_name, result=None, error=error_text
                    )

                # For successful results, extract text content from CallToolResult
                success_messages = mcp_client.extract_text_content(call_result)
                result_text = (
                    " ".join(success_messages)
                    if success_messages
                    else "MCP tool completed successfully with no text output"
                )
                return ToolResult(
                    tool_name=tool_name, result=result_text, error=None
                )

            else:
                # Unknown tool source
                system_error = f"Unknown tool source: {tool.source} for tool {tool_name}. Supported sources are: backend, frontend, mcp."
                LOGGER.error(system_error)
                return ToolResult(
                    tool_name=tool_name,
                    result=None,
                    error=f"Internal error: Tool configuration error for tool {tool_name}.",
                )

        except Exception as e:
            error_message = f"Error invoking tool '{tool_name}': {str(e)}"
            LOGGER.error(error_message)
            return ToolResult(
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
        from marimo._server.ai.mcp import get_mcp_client

        mcp_client = get_mcp_client()

        # Create properly typed parameters for the MCP tool
        params = mcp_client.create_tool_params(tool_name, arguments)

        # Invoke the tool
        call_result = await mcp_client.invoke_tool(tool_name, params)

        # Return the CallToolResult directly - let invoke_tool handle error checking
        return call_result

    def _register_builtin_tools(self) -> None:
        """Register built-in backend tools."""
        # Register all backend tools from the backend_tools package
        from marimo._server.ai.backend_tools import register_all_backend_tools

        register_all_backend_tools()


# Global tool manager instance using lazy initialization to avoid circular imports
_TOOL_MANAGER: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """Get the global tool manager instance, initializing it if needed."""
    global _TOOL_MANAGER
    if _TOOL_MANAGER is None:
        _TOOL_MANAGER = ToolManager()
        # Register tools after the manager is created to avoid circular imports
        _TOOL_MANAGER._register_builtin_tools()
        LOGGER.info(
            f"ToolManager initialized with {len(_TOOL_MANAGER._tools)} backend/frontend tools"
        )
    return _TOOL_MANAGER
