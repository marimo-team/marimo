# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_MCP_CONFIG,
    MCPConfig,
    MCPServerConfig,
    MCPServerStdioConfig,
    MCPServerStreamableHttpConfig,
)
from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from typing import Protocol, TypedDict

    from anyio.streams.memory import (
        MemoryObjectReceiveStream,
        MemoryObjectSendStream,
    )
    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.shared.message import SessionMessage
    from mcp.types import (  # type: ignore[import-not-found]
        CallToolRequestParams,
        CallToolResult,
        ListToolsResult,
        Tool,
    )

    class MCPToolMeta(TypedDict):
        """Metadata that marimo adds to MCP tools."""

        server_name: str
        namespaced_name: str

    class MCPToolWithMeta(Protocol):
        """MCP Tool with marimo-specific metadata."""

        name: str
        description: str | None
        inputSchema: dict[str, Any]
        meta: MCPToolMeta


# Type alias that matches the MCP SDK's CallToolRequestParams.arguments type
MCPToolArgs = Optional[dict[str, Any]]

# Type alias for MCP transport connection streams
TransportConnectorResponse = tuple[
    "MemoryObjectReceiveStream[Union[SessionMessage, Exception]]",
    "MemoryObjectSendStream[SessionMessage]",
]

LOGGER = _loggers.marimo_logger()


class MCPTransportType(str, Enum):
    """Supported MCP transport types."""

    # based on https://modelcontextprotocol.io/docs/concepts/transports
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPServerStatus(Enum):
    """Status of an MCP server connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPServerDefinition:
    """Runtime server definition wrapping config with computed fields."""

    name: str
    transport: MCPTransportType
    config: MCPServerConfig
    timeout: float = 30.0


class MCPServerDefinitionFactory:
    """Factory for creating transport-specific server definitions."""

    @classmethod
    def from_config(
        cls, name: str, config: MCPServerConfig
    ) -> MCPServerDefinition:
        """Create server definition with automatic transport detection.

        Args:
            name: Server name
            config: Server configuration from config file

        Returns:
            Server definition with detected transport type

        Raises:
            ValueError: If configuration type is not supported
        """
        # Import here to avoid circular imports

        if "command" in config:
            return MCPServerDefinition(
                name=name,
                transport=MCPTransportType.STDIO,
                config=config,
                timeout=30.0,  # default timeout for STDIO
            )
        elif "url" in config:
            return MCPServerDefinition(
                name=name,
                transport=MCPTransportType.STREAMABLE_HTTP,
                config=config,
                timeout=config.get("timeout") or 30.0,
            )
        else:
            raise ValueError(f"Unsupported config type: {type(config)}")


class MCPTransportConnector(ABC):
    """Abstract base class for MCP transport connectors."""

    @abstractmethod
    async def connect(
        self, server_def: MCPServerDefinition, exit_stack: AsyncExitStack
    ) -> TransportConnectorResponse:
        """Connect to the MCP server and return read/write streams.

        Args:
            server_def: Server definition with transport-specific parameters
            exit_stack: Async exit stack for resource management

        Returns:
            Tuple of (read_stream, write_stream) for the ClientSession
        """
        pass


class StdioTransportConnector(MCPTransportConnector):
    """STDIO transport connector for process-based MCP servers."""

    async def connect(
        self, server_def: MCPServerDefinition, exit_stack: AsyncExitStack
    ) -> TransportConnectorResponse:
        # Import MCP SDK components for stdio transport
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Type narrowing for mypy
        assert "command" in server_def.config
        config = cast(MCPServerStdioConfig, server_def.config)

        # Set up environment variables for the server process
        env = os.environ.copy()
        env.update(config.get("env") or {})

        # Configure server parameters
        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args") or [],
            env=env,
        )

        # Establish connection with proper resource management
        read, write, *_ = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        return read, write


class StreamableHTTPTransportConnector(MCPTransportConnector):
    """Streamable HTTP transport connector for modern HTTP-based MCP servers."""

    async def connect(
        self, server_def: MCPServerDefinition, exit_stack: AsyncExitStack
    ) -> TransportConnectorResponse:
        # Import MCP SDK components for streamable HTTP transport
        from mcp.client.streamable_http import streamablehttp_client

        # Type narrowing for mypy
        assert "url" in server_def.config
        config = cast(MCPServerStreamableHttpConfig, server_def.config)

        # Establish streamable HTTP connection
        read, write, *_ = await exit_stack.enter_async_context(
            streamablehttp_client(
                config["url"],
                headers=config.get("headers") or {},
                timeout=server_def.timeout,
            )
        )

        return read, write


class MCPTransportRegistry:
    """Registry for MCP transport connectors."""

    def __init__(self) -> None:
        self._connectors: dict[MCPTransportType, MCPTransportConnector] = {
            MCPTransportType.STDIO: StdioTransportConnector(),
            MCPTransportType.STREAMABLE_HTTP: StreamableHTTPTransportConnector(),
        }

    def get_connector(
        self, transport_type: MCPTransportType
    ) -> MCPTransportConnector:
        """Get the appropriate transport connector for the given transport type.

        Args:
            transport_type: The type of transport to connect with

        Returns:
            Transport connector instance

        Raises:
            ValueError: If transport type is not supported
        """
        if transport_type not in self._connectors:
            raise ValueError(f"Unsupported transport type: {transport_type}")
        return self._connectors[transport_type]


@dataclass
class MCPServerConnection:
    """Represents a connection to an MCP server."""

    definition: MCPServerDefinition
    session: Optional[ClientSession] = None
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    tools: list[Tool] = field(default_factory=list)
    last_health_check: float = 0
    error_message: Optional[str] = None
    read_stream: Optional[
        MemoryObjectReceiveStream[Union[SessionMessage, Exception]]
    ] = None
    write_stream: Optional[MemoryObjectSendStream[SessionMessage]] = None
    exit_stack: Optional[AsyncExitStack] = None


class MCPClient:
    """Client for managing connections to multiple MCP servers."""

    def __init__(self, config: Optional[MCPConfig] = None):
        """Initialize MCP client with server configuration."""
        self.config: MCPConfig = config or MCPConfig(mcpServers={})
        self.servers: dict[str, MCPServerDefinition] = {}
        self.connections: dict[str, MCPServerConnection] = {}
        self.tool_registry: dict[str, Tool] = {}
        self.server_counters: dict[
            str, int
        ] = {}  # For handling naming conflicts
        self.transport_registry = MCPTransportRegistry()
        self.health_check_tasks: dict[str, asyncio.Task[None]] = {}
        self.health_check_interval: float = 30.0  # seconds
        self.health_check_timeout: float = (
            5.0  # seconds - shorter timeout for health checks
        )
        self._parse_config()

    def _parse_config(self) -> None:
        """Parse MCP server configuration.

        Note: Servers with invalid configurations are logged but excluded from self.servers,
        making them unavailable for connection attempts.
        """
        mcp_servers = self.config.get("mcpServers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                server_def = MCPServerDefinitionFactory.from_config(
                    server_name, server_config
                )

                self.servers[server_name] = server_def
                LOGGER.debug(
                    f"Registered MCP server: {server_name} (transport: {server_def.transport})"
                )
            except KeyError as e:
                LOGGER.error(
                    f"Invalid configuration for server {server_name}: missing {e}"
                )
                # Note: Server with invalid configuration is not added to self.servers
            except ValueError as e:
                LOGGER.error(
                    f"Invalid configuration for server {server_name}: {e}"
                )
                # Note: Server with invalid configuration is not added to self.servers

    async def connect_to_server(self, server_name: str) -> bool:
        """Connect to an MCP server using the appropriate transport."""
        # Import common MCP SDK components
        from mcp import ClientSession

        if server_name not in self.servers:
            LOGGER.error(f"Server {server_name} not found in configuration")
            return False

        server_def = self.servers[server_name]

        # Check if already connected
        if server_name in self.connections:
            # Use public API to check status
            current_status = self.get_server_status(server_name)
            if current_status == MCPServerStatus.CONNECTED:
                return True

        try:
            # Create connection
            connection = MCPServerConnection(definition=server_def)
            self.connections[server_name] = connection
            self._update_server_status(server_name, MCPServerStatus.CONNECTING)

            # Clean up old tools before discovering new ones (handles server updates/restarts)
            self._remove_server_tools(server_name)

            # Create exit stack for proper resource management
            connection.exit_stack = AsyncExitStack()

            LOGGER.info(
                f"Connecting to MCP server: {server_name} (transport: {server_def.transport})"
            )

            # Get the appropriate transport connector and establish connection
            transport_connector = self.transport_registry.get_connector(
                server_def.transport
            )
            read, write, *_ = await transport_connector.connect(
                server_def, connection.exit_stack
            )

            connection.read_stream = read
            connection.write_stream = write

            # Create and initialize session
            connection.session = (
                await connection.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
            )

            # Initialize the session
            if connection.session is None:
                raise RuntimeError("Session was not properly created")
            await connection.session.initialize()

            self._update_server_status(server_name, MCPServerStatus.CONNECTED)

            await self._discover_tools(connection)

            # Start health monitoring for this server
            if server_name not in self.health_check_tasks:
                self.health_check_tasks[server_name] = asyncio.create_task(
                    self._monitor_server_health(server_name)
                )

            LOGGER.info(
                f"Successfully connected to MCP server: {server_name} (transport: {server_def.transport})"
            )
            return True

        except Exception as e:
            error_msg = f"Failed to connect to MCP server {server_name} (transport: {server_def.transport}): {str(e)}"
            LOGGER.error(error_msg)

            # Clean up exit_stack if connection was created but failed
            if server_name in self.connections:
                connection = self.connections[server_name]
                if connection.exit_stack:
                    try:
                        await connection.exit_stack.aclose()
                    except Exception as cleanup_error:
                        LOGGER.warning(
                            f"Error during cleanup for {server_name}: {cleanup_error}"
                        )
                    connection.exit_stack = None

                self._update_server_status(
                    server_name, MCPServerStatus.ERROR, error_msg
                )
            return False

    async def _discover_tools(self, connection: MCPServerConnection) -> None:
        """Discover tools from an MCP server."""
        try:
            LOGGER.info(
                f"Discovering tools for server: {connection.definition.name}"
            )

            if not connection.session:
                raise RuntimeError("No active session for tool discovery")

            # Use the MCP SDK to discover tools
            tools_response: ListToolsResult = (
                await connection.session.list_tools()
            )

            # Add discovered tools
            self._add_server_tools(connection, tools_response.tools)

            LOGGER.info(
                f"Discovered {len(connection.tools)} tools from {connection.definition.name}"
            )

        except Exception as e:
            LOGGER.error(
                f"Tool discovery failed for {connection.definition.name}: {str(e)}"
            )

    def _create_namespaced_tool_name(
        self, server_name: str, tool_name: str
    ) -> str:
        """Create a namespaced tool name with conflict resolution."""
        base_name = f"mcp_{server_name}_{tool_name}"

        # Check for conflicts
        if base_name not in self.tool_registry:
            return base_name

        # Handle naming conflicts - add readable counter to group tools from the same server
        # The existing tool keeps the base name, current tool gets a numbered name
        # e.g. mcp_server_name_tool_name, mcp_server_name1_tool_name, mcp_server_name2_tool_name, ...
        # Based on the vscode MCP tool naming strategy:
        # https://github.com/microsoft/vscode/issues/244644#issuecomment-2932206637
        counter = self.server_counters.get(server_name, 0) + 1
        self.server_counters[server_name] = counter
        return f"mcp_{server_name}{counter}_{tool_name}"

    async def connect_to_all_servers(self) -> dict[str, bool]:
        """Connect to all configured MCP servers."""
        results = {}

        # Connect to servers concurrently
        tasks = [
            self.connect_to_server(server_name)
            for server_name in self.servers.keys()
        ]

        connection_results = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        for server_name, result in zip(
            self.servers.keys(), connection_results
        ):
            if isinstance(result, Exception):
                LOGGER.error(f"Failed to connect to {server_name}: {result}")
                results[server_name] = False
            else:
                results[server_name] = bool(result)

        return results

    def _create_error_result(self, error_message: str) -> CallToolResult:
        """Create a properly formatted error CallToolResult

        Args:
            error_message: The error message to include

        Returns:
            CallToolResult with isError=True and the error message
        """
        # Based on the MCP SDK error handling:
        # https://modelcontextprotocol.io/docs/concepts/tools#error-handling
        from mcp.types import CallToolResult, TextContent

        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=error_message)],
        )

    def is_error_result(self, result: CallToolResult) -> bool:
        """Check if a CallToolResult represents an error."""
        return hasattr(result, "isError") and result.isError is True

    async def invoke_tool(
        self, namespaced_tool_name: str, params: CallToolRequestParams
    ) -> CallToolResult:
        """Invoke an MCP tool using properly typed CallToolRequestParams."""
        tool = self.tool_registry.get(namespaced_tool_name)
        if not tool:
            # Return validation error as CallToolResult instead of raising
            return self._create_error_result(
                f"Tool '{namespaced_tool_name}' not found"
            )

        # Validate that the params tool name matches the resolved tool name
        if params.name != tool.name:
            return self._create_error_result(
                f"Internal error: Parameter tool name '{params.name}' does not match resolved tool name '{tool.name}'"
            )

        # Get server_name from meta field
        server_name = tool.meta.get("server_name") if tool.meta else None
        if not server_name:
            return self._create_error_result(
                f"Internal error: Tool '{namespaced_tool_name}' missing server information"
            )

        if self.get_server_status(server_name) != MCPServerStatus.CONNECTED:
            return self._create_error_result(
                f"Server '{server_name}' is not connected"
            )

        connection = self.connections.get(server_name)
        if not connection or not connection.session:
            return self._create_error_result(
                f"Internal error: No active session for server '{server_name}'"
            )

        try:
            LOGGER.debug(
                f"Invoking MCP tool with params: {namespaced_tool_name}"
            )

            # Use asyncio.wait_for for timeout handling
            timeout = connection.definition.timeout
            result = await asyncio.wait_for(
                connection.session.call_tool(params.name, params.arguments),
                timeout=timeout,
            )

            # Validate the result
            if not result:
                LOGGER.warning(
                    f"Tool {namespaced_tool_name} returned empty result"
                )
                return self._create_error_result("Tool returned empty result")

            # Return the MCP SDK result directly (may already have isError=True)
            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool {namespaced_tool_name} timed out after {connection.definition.timeout} seconds"
            LOGGER.error(error_msg)

            return self._create_error_result(
                f"Tool execution timed out after {connection.definition.timeout} seconds"
            )

        except Exception as e:
            LOGGER.error(
                f"Failed to invoke tool {namespaced_tool_name} with params: {str(e)}"
            )

            return self._create_error_result(
                f"Tool execution failed: {str(e)}"
            )

    def create_tool_params(
        self, namespaced_tool_name: str, arguments: MCPToolArgs = None
    ) -> CallToolRequestParams:
        """Create properly typed CallToolRequestParams for a tool."""
        from mcp.types import CallToolRequestParams

        tool = self.tool_registry.get(namespaced_tool_name)
        if not tool:
            raise ValueError(f"Tool '{namespaced_tool_name}' not found")

        return CallToolRequestParams(name=tool.name, arguments=arguments)

    def extract_text_content(self, result: CallToolResult) -> list[str]:
        """Extract text content from a CallToolResult, handling both success and error cases."""
        # Import TextContent at runtime for isinstance check
        from mcp.types import TextContent

        if not hasattr(result, "content") or not result.content:
            LOGGER.warning("CallToolResult has no content")
            return []

        text_contents: list[str] = []

        for content_item in result.content:
            # Use isinstance with the actual TextContent type for proper type checking
            if isinstance(content_item, TextContent):
                text_contents.append(content_item.text)
            else:
                # Log unexpected content types for debugging
                LOGGER.debug(
                    f"Unexpected content type in CallToolResult. We only support TextContent: {type(content_item)}"
                )

        # Log if this was an error result (for debugging purposes)
        if hasattr(result, "isError") and result.isError:
            LOGGER.debug(
                f"Extracted text content from error result: {len(text_contents)} items"
            )

        return text_contents

    def get_all_tools(self) -> list[Tool]:
        """Get all registered MCP tools."""
        return list(self.tool_registry.values())

    def get_tools_by_server(self, server_name: str) -> list[Tool]:
        """Get tools from a specific server."""
        return [
            tool
            for tool in self.tool_registry.values()
            if tool.meta and tool.meta.get("server_name") == server_name
        ]

    def get_server_status(self, server_name: str) -> Optional[MCPServerStatus]:
        """Get the status of a specific server."""
        connection = self.connections.get(server_name)
        return connection.status if connection else None

    def get_all_server_statuses(self) -> dict[str, MCPServerStatus]:
        """Get the status of all servers."""
        return {name: conn.status for name, conn in self.connections.items()}

    async def _monitor_server_health(self, server_name: str) -> None:
        """Continuously monitor server health."""
        try:
            while True:
                try:
                    await asyncio.sleep(self.health_check_interval)

                    # Use the public API to check server status
                    current_status = self.get_server_status(server_name)
                    if current_status != MCPServerStatus.CONNECTED:
                        continue

                    # Perform health check
                    health_check_passed = await self._perform_health_check(
                        server_name
                    )

                    if health_check_passed:
                        # Handle successful health check
                        LOGGER.debug(f"Health check passed for {server_name}")
                        connection = self.connections.get(server_name)
                        if connection:
                            # Update last health check time
                            connection.last_health_check = time.time()
                    else:
                        # Handle failed health check
                        LOGGER.warning(
                            f"Health check failed for {server_name}, marking as ERROR and removing from monitoring"
                        )

                        # Determine the appropriate error message based on connection state
                        connection = self.connections.get(server_name)
                        if connection and not connection.session:
                            error_msg = "No active session"
                        else:
                            error_msg = "Health check failed"

                        # Update server status and remove tools
                        self._update_server_status(
                            server_name, MCPServerStatus.ERROR, error_msg
                        )
                        self._remove_server_tools(server_name)
                        break  # Exit monitoring loop on failure

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    LOGGER.error(
                        f"Health monitoring error for {server_name}: {e}"
                    )
                    break  # Exit monitoring loop on unexpected error
        finally:
            # Clean up the monitoring task from the registry
            # Note: Don't cancel here since the task is already exiting
            if server_name in self.health_check_tasks:
                del self.health_check_tasks[server_name]
                LOGGER.debug(
                    f"Removed health monitoring task for {server_name}"
                )

    async def _perform_health_check(self, server_name: str) -> bool:
        """Perform health check for a server and update its status"""
        connection = self.connections.get(server_name)
        if not connection:
            return False

        try:
            if not connection.session:
                return False

            # Use official MCP ping method for health check
            # https://modelcontextprotocol.io/specification/2025-03-26/basic/utilities/ping
            await asyncio.wait_for(
                connection.session.send_ping(),
                timeout=self.health_check_timeout,
            )

            return True

        except asyncio.TimeoutError:
            LOGGER.warning(
                f"Health check ping timed out after {self.health_check_timeout} seconds for {server_name}"
            )
            return False
        except Exception as e:
            LOGGER.warning(f"Health check failed for {server_name}: {e}")
            return False

    def _update_server_status(
        self,
        server_name: str,
        status: MCPServerStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Centralized method to update server status.

        Args:
            server_name: Name of the server
            status: New status to set
            error_message: Optional error message for ERROR status
        """
        connection = self.connections.get(server_name)
        if not connection:
            return

        connection.status = status
        connection.error_message = error_message

    def _add_server_tools(
        self, connection: MCPServerConnection, tools: list[Tool]
    ) -> None:
        """Add tools from a server to the registry and connection.

        Args:
            connection: Server connection to add tools to
            tools: List of raw MCP tools to add
        """
        from mcp.types import Tool  # type: ignore[import-not-found]

        server_name = connection.definition.name

        for tool in tools:
            namespaced_name = self._create_namespaced_tool_name(
                server_name, tool.name
            )

            # Create MCP tool with metadata
            # Note: MCP SDK Tool constructor uses _meta parameter (with underscore)
            # but exposes the data as .meta attribute (without underscore) after creation
            mcp_tool = Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.inputSchema,
                _meta={
                    "server_name": server_name,
                    "namespaced_name": namespaced_name,
                },
            )

            # Add to connection and registry
            connection.tools.append(mcp_tool)
            self.tool_registry[namespaced_name] = mcp_tool

        LOGGER.debug(f"Added {len(tools)} tools from {server_name}")

    def _remove_server_tools(self, server_name: str) -> None:
        """Remove all tools from a server from the registry and clear connection tools.

        Args:
            server_name: Server name to remove tools for.
        """
        tools_to_remove = [
            name
            for name, tool in self.tool_registry.items()
            if tool.meta and tool.meta.get("server_name") == server_name
        ]

        if tools_to_remove:
            for tool_name in tools_to_remove:
                del self.tool_registry[tool_name]
            LOGGER.debug(
                f"Removed {len(tools_to_remove)} tools from {server_name}"
            )

        # Also clear tools from the connection object if it exists
        connection = self.connections.get(server_name)
        if connection:
            connection.tools.clear()

        # Reset the server counter so reconnection starts with clean tool names
        self._reset_server_counter(server_name)

    def _reset_server_counter(self, server_name: str) -> None:
        """Reset the naming counter for a server to allow clean reconnection.

        Args:
            server_name: Server name to reset counter for.
        """
        if server_name in self.server_counters:
            del self.server_counters[server_name]
            LOGGER.debug(f"Reset naming counter for {server_name}")

    async def _cancel_health_monitoring(
        self, server_name: Optional[str] = None
    ) -> None:
        """Cancel health monitoring for a specific server or all servers.

        Args:
            server_name: Server name to cancel monitoring for. If None, cancels all.
        """
        if server_name is not None:
            # Cancel single server monitoring
            if server_name in self.health_check_tasks:
                task = self.health_check_tasks[server_name]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del self.health_check_tasks[server_name]
                LOGGER.debug(f"Cancelled health monitoring for {server_name}")
        else:
            # Cancel all server monitoring
            if self.health_check_tasks:
                # Cancel all tasks
                for task in self.health_check_tasks.values():
                    task.cancel()

                # Wait for all tasks to complete
                await asyncio.gather(
                    *self.health_check_tasks.values(), return_exceptions=True
                )
                self.health_check_tasks.clear()
                LOGGER.debug("Cancelled all health monitoring tasks")

    async def disconnect_from_server(self, server_name: str) -> bool:
        """Disconnect from a specific MCP server."""
        connection = self.connections.get(server_name)
        if not connection:
            return True

        try:
            # Cancel health monitoring task
            await self._cancel_health_monitoring(server_name)

            # Close exit stack which will properly close the session and streams
            if connection.exit_stack:
                await connection.exit_stack.aclose()

            # Remove tools from registry
            self._remove_server_tools(server_name)

            self._update_server_status(
                server_name, MCPServerStatus.DISCONNECTED
            )
            connection.session = None
            connection.read_stream = None
            connection.write_stream = None
            connection.exit_stack = None

            LOGGER.info(f"Disconnected from MCP server: {server_name}")
            return True

        except Exception as e:
            LOGGER.error(
                f"Error disconnecting from server {server_name}: {str(e)}"
            )
            return False

    async def disconnect_from_all_servers(self) -> None:
        """Disconnect from all MCP servers."""
        # Cancel all health monitoring tasks first
        await self._cancel_health_monitoring()

        # Disconnect from all servers
        tasks = [
            self.disconnect_from_server(server_name)
            for server_name in list(self.connections.keys())
        ]

        await asyncio.gather(*tasks, return_exceptions=True)


# Global MCP client instance using lazy initialization
_MCP_CLIENT: Optional[MCPClient] = None


def get_mcp_client(config: Optional[MCPConfig] = None) -> MCPClient:
    """Get the global MCP client instance, initializing it if needed."""
    global _MCP_CLIENT
    if _MCP_CLIENT is None:
        try:
            DependencyManager.mcp.require(why="for MCP server connections")
        except ModuleNotFoundError as e:
            LOGGER.info(f"MCP SDK not available: {str(e)}")
            raise

        _MCP_CLIENT = MCPClient(config or _get_default_config())
        LOGGER.info("MCP client initialized")
    return _MCP_CLIENT


def _get_default_config() -> MCPConfig:
    """Get default MCP configuration."""
    return DEFAULT_MCP_CONFIG
