# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from marimo import _loggers
from marimo._config.config import CopilotMode

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
    """Centralized manager for all tools (mcp, backend, frontend)."""

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

    def register_mcp_tool(self, tool: Tool) -> None:
        """Register an MCP tool (no local handler needed)."""
        if tool.source != "mcp":
            raise ValueError("Tool source must be 'mcp'")

        self._tools[tool.name] = tool
        LOGGER.debug(f"Registered MCP tool: {tool.name}")

    def get_tools_for_mode(self, mode: CopilotMode) -> list[Tool]:
        """Get all tools available for a specific mode."""
        return [tool for tool in self._tools.values() if mode in tool.mode]

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool definition by name."""
        return self._tools.get(name)

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

    def create_system_llm_error(self, error_message: str) -> str:
        """Create an LLM error message for a tool."""
        return f"{error_message} Please file a GitHub issue if this problem persists."

    async def invoke_tool(
        self, tool_name: str, arguments: FunctionArgs
    ) -> ToolResult:
        """Invoke a tool by name and return the result."""
        tool = self.get_tool(tool_name)

        if not tool:
            available_tools = list(self._tools.keys())
            return ToolResult(
                tool_name=tool_name,
                result=None,
                error=f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}",
            )

        if tool.source == "frontend":
            system_error = f"Frontend tool '{tool_name}' cannot be invoked in the backend. Frontend tools must be executed in the client."
            LOGGER.error(system_error)
            return ToolResult(
                tool_name=tool_name,
                result=None,
                error=self.create_system_llm_error(
                    f"Tool '{tool_name}' is a frontend tool and cannot be executed on the server."
                ),
            )

        # Validate arguments for backend tools
        if tool.source == "backend":
            is_valid, validation_error = self.validate_backend_tool_arguments(
                tool_name, arguments
            )
            if not is_valid:
                return ToolResult(
                    tool_name=tool_name,
                    result=None,
                    error=f"Invalid arguments for tool '{tool_name}': {validation_error}",
                )

        try:
            if tool.source == "backend":
                # Handle backend tools
                handler = self._backend_handlers.get(tool_name)
                if not handler:
                    system_error = (
                        f"No handler found for backend tool '{tool_name}'."
                    )
                    LOGGER.error(system_error)
                    return ToolResult(
                        tool_name=tool_name,
                        result=None,
                        error=self.create_system_llm_error(
                            f"Tool '{tool_name}' cannot be invoked."
                        ),
                    )
                result = await self._call_handler(handler, arguments)

            elif tool.source == "mcp":
                # Handle MCP tools
                result = await self._invoke_mcp_tool(tool_name, arguments)

            else:
                # Unknown tool source
                system_error = f"Unknown tool source: {tool.source} for tool {tool_name}. Supported sources are: backend, frontend, mcp."
                LOGGER.error(system_error)
                return ToolResult(
                    tool_name=tool_name,
                    result=None,
                    error=self.create_system_llm_error(
                        f"Tool configuration error for tool {tool_name}."
                    ),
                )

            return ToolResult(tool_name=tool_name, result=result, error=None)

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
    ) -> Any:
        """Invoke an MCP tool via the MCP client."""
        # TODO: Implement MCP tool invocation
        # This would interact with the MCP client to call the tool
        LOGGER.warning(
            f"MCP tool invocation not yet implemented for '{tool_name}'"
        )
        return {
            "message": f"MCP tool '{tool_name}' called with args: {arguments}"
        }

    def _register_builtin_tools(self) -> None:
        """Register built-in backend tools."""
        # Register all backend tools from the backend_tools package
        from marimo._server.ai.backend_tools import register_all_backend_tools

        register_all_backend_tools()

    def _discover_mcp_tools(self) -> None:
        """Discover and register MCP tools."""
        # TODO: Implement MCP tool discovery
        # This would connect to MCP servers and get their available tools
        LOGGER.debug("MCP tool discovery not yet implemented")


# Global tool manager instance using lazy initialization to avoid circular imports
_TOOL_MANAGER: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """Get the global tool manager instance, initializing it if needed."""
    global _TOOL_MANAGER
    if _TOOL_MANAGER is None:
        _TOOL_MANAGER = ToolManager()
        # Register tools after the manager is created to avoid circular imports
        _TOOL_MANAGER._register_builtin_tools()
        _TOOL_MANAGER._discover_mcp_tools()
        LOGGER.info(
            f"ToolManager initialized with {len(_TOOL_MANAGER._tools)} tools"
        )
    return _TOOL_MANAGER
