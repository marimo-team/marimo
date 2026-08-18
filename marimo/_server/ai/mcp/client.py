# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._config.config import MCPConfig
from marimo._server.ai.mcp.config import (
    MCPConfigComparator,
    MCPServerDefinition,
    MCPServerDefinitionFactory,
    append_presets,
)
from marimo._server.ai.mcp.transport import (
    MCPTransportRegistry,
)
from marimo._server.ai.mcp.types import MCPToolArgs
from marimo._utils.asyncio_utils import cancel_and_wait, supervised_task

if TYPE_CHECKING:
    from typing import Protocol

    from mcp import Client as MCPConnectionClient
    from mcp.types import (  # type: ignore[import-not-found]
        CallToolRequestParams,
        CallToolResult,
        ListToolsResult,
        Tool,
    )

    class _StructuredContentResult(Protocol):
        @property
        def structured_content(self) -> object | None: ...

    class _MetadataCarrier(Protocol):
        @property
        def meta(self) -> dict[str, object] | None: ...


LOGGER = _loggers.marimo_logger()


def _get_structured_content(
    result: _StructuredContentResult,
) -> object | None:
    return result.structured_content


def _get_metadata(value: _MetadataCarrier) -> dict[str, object]:
    return dict(value.meta or {})


class MCPServerStatus(Enum):
    """Status of an MCP server connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPServerConnection:
    """Represents a connection to an MCP server."""

    definition: MCPServerDefinition
    client: MCPConnectionClient | None = None
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    tools: list[Tool] = field(default_factory=list)
    last_health_check: float = 0
    error_message: str | None = None
    # The task owns the client's async context from connection through cleanup.
    connection_task: asyncio.Task[None] | None = None
    disconnect_event: asyncio.Event | None = None
    connection_event: asyncio.Event | None = None


class MCPClient:
    """Client for managing connections to multiple MCP servers."""

    def __init__(self) -> None:
        """Initialize MCP client.

        Note: For dynamic reconfiguration, use await client.configure(new_config)
              which will handle adding/removing/updating connections automatically.
        """
        self.servers: dict[str, MCPServerDefinition] = {}
        self.connections: dict[str, MCPServerConnection] = {}
        self.tool_registry: dict[str, Tool] = {}
        self.server_counters: dict[
            str, int
        ] = {}  # For handling naming conflicts
        self.transport_registry: MCPTransportRegistry = MCPTransportRegistry()
        self.health_check_tasks: dict[str, asyncio.Task[None]] = {}
        self.health_check_interval: float = 30.0  # seconds
        self.health_check_timeout: float = (
            5.0  # seconds - shorter timeout for health checks
        )
        self.health_check_failure_threshold: int = 3

    async def configure(self, config: MCPConfig) -> None:
        """Configure the MCP client with the given configuration.

        This method:
        1. Parses the new configuration
        2. Compares it with current configuration
        3. Disconnects from removed servers
        4. Disconnects and reconnects to updated servers
        5. Connects to new servers

        Args:
            config: MCP configuration to apply
        """
        # Parse new configuration
        new_servers = self._parse_config(config)

        # Compute differences
        diff = MCPConfigComparator.compute_diff(self.servers, new_servers)

        # Early return if no changes
        if not diff.has_changes():
            LOGGER.debug(
                "MCP configuration unchanged, skipping reconfiguration"
            )
            return

        LOGGER.info(
            "MCP configuration changed: %d to add, %d to remove, %d to update, %d unchanged",
            len(diff.servers_to_add),
            len(diff.servers_to_remove),
            len(diff.servers_to_update),
            len(diff.servers_unchanged),
        )

        # Disconnect from removed servers
        for server_name in diff.servers_to_remove:
            LOGGER.info(f"Removing server: {server_name}")
            await self.disconnect_from_server(server_name)
            # Clean up from servers and connections registries
            if server_name in self.servers:
                del self.servers[server_name]
            if server_name in self.connections:
                del self.connections[server_name]

        # Disconnect from servers that need to be updated (will reconnect below)
        for server_name in diff.servers_to_update:
            LOGGER.info(f"Updating server: {server_name}")
            await self.disconnect_from_server(server_name)
            # Clean up old connection, will be recreated below
            if server_name in self.connections:
                del self.connections[server_name]

        # Update servers registry with new configuration
        # Add new servers
        self.servers.update(diff.servers_to_add)
        # Update modified servers
        self.servers.update(diff.servers_to_update)

        # Connect to new and updated servers
        servers_to_connect = {**diff.servers_to_add, **diff.servers_to_update}

        if servers_to_connect:
            # Connect to servers concurrently
            tasks = [
                self.connect_to_server(server_name)
                for server_name in servers_to_connect
            ]
            connection_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            for server_name, result in zip(
                servers_to_connect.keys(), connection_results, strict=False
            ):
                if isinstance(result, Exception):
                    LOGGER.error(
                        f"Failed to connect to {server_name}: {result}"
                    )
                elif not result:
                    LOGGER.warning(
                        f"Connection to {server_name} did not succeed"
                    )

    def _parse_config(
        self, config: MCPConfig
    ) -> dict[str, MCPServerDefinition]:
        """Parse MCP server configuration.

        Note: Servers with invalid configurations are logged but excluded from returned dict,
        making them unavailable for connection attempts.

        Args:
            config: MCP configuration to parse

        Returns:
            Dictionary of server name to server definition for valid servers
        """
        # Apply presets before parsing
        config = append_presets(config)
        mcp_servers = config.get("mcpServers", {})
        parsed_servers: dict[str, MCPServerDefinition] = {}

        for server_name, server_config in mcp_servers.items():
            try:
                server_def = MCPServerDefinitionFactory.from_config(
                    server_name, server_config
                )

                parsed_servers[server_name] = server_def
                LOGGER.debug(
                    f"Parsed MCP server: {server_name} (transport: {server_def.transport})"
                )
            except KeyError as e:
                LOGGER.error(
                    f"Invalid configuration for server {server_name}: missing {e}"
                )
                # Note: Server with invalid configuration is not added to parsed_servers
            except ValueError as e:
                LOGGER.error(
                    f"Invalid configuration for server {server_name}: {e}"
                )
                # Note: Server with invalid configuration is not added to parsed_servers

        return parsed_servers

    async def _connection_lifecycle(self, server_name: str) -> None:
        """Run a task-owned MCP client connection until disconnected."""
        from mcp import Client

        connection = self.connections.get(server_name)
        if not connection:
            return

        server_def = connection.definition

        try:
            transport_connector = self.transport_registry.get_connector(
                server_def.transport
            )
            mcp_client = Client(
                transport_connector.create(server_def),
                mode="auto",
                read_timeout_seconds=server_def.timeout,
            )

            # MCP transports use task-affine AnyIO cancel scopes. The lifecycle
            # task must both enter and exit the client context.
            async with mcp_client:
                connection.client = mcp_client
                LOGGER.info(
                    f"Connecting to MCP server: {server_name} (transport: {server_def.transport})"
                )

                await self._discover_tools(connection)
                self._update_server_status(
                    server_name, MCPServerStatus.CONNECTED
                )

                if server_name not in self.health_check_tasks:
                    self.health_check_tasks[server_name] = supervised_task(
                        self._monitor_server_health(server_name),
                        name=f"mcp.health.{server_name}",
                    )

                # Signal that connection is established
                if connection.connection_event:
                    connection.connection_event.set()

                LOGGER.info(
                    f"Successfully connected to MCP server: {server_name} (transport: {server_def.transport})"
                )

                # Wait for disconnect signal
                if connection.disconnect_event:
                    await connection.disconnect_event.wait()

                # Cancel health monitoring
                await self._cancel_health_monitoring(server_name)

        except Exception as e:
            error_msg = f"Failed to connect to MCP server {server_name} (transport: {server_def.transport}): {e!s}"
            LOGGER.error(error_msg)
            self._update_server_status(
                server_name, MCPServerStatus.ERROR, error_msg
            )

            # Signal connection event so connect_to_server doesn't wait unnecessarily
            if connection and connection.connection_event:
                connection.connection_event.set()
        finally:
            # Clean up connection state
            self._remove_server_tools(server_name)
            if connection.status != MCPServerStatus.ERROR:
                self._update_server_status(
                    server_name, MCPServerStatus.DISCONNECTED
                )
            connection.client = None

    async def connect_to_server(self, server_name: str) -> bool:
        """Connect to an MCP server using the appropriate transport."""
        if server_name not in self.servers:
            LOGGER.error(f"Server {server_name} not found in configuration")
            return False

        server_def = self.servers[server_name]

        existing_connection = self.connections.get(server_name)
        if existing_connection:
            current_status = self.get_server_status(server_name)
            if current_status == MCPServerStatus.CONNECTED:
                return True
            if existing_connection.connection_task:
                await self.disconnect_from_server(server_name)

        try:
            # Create connection with minimal task-per-connection additions
            disconnect_event = asyncio.Event()
            connection_event = asyncio.Event()
            connection = MCPServerConnection(
                definition=server_def,
                disconnect_event=disconnect_event,
                connection_event=connection_event,
            )
            self.connections[server_name] = connection
            self._update_server_status(server_name, MCPServerStatus.CONNECTING)
            self._remove_server_tools(server_name)

            # Create task to run existing connection logic. Not supervised:
            # this task is awaited in disconnect_from_server(), so supervisor
            # logging would duplicate the awaiter's error handling.
            connection_task = asyncio.create_task(
                self._connection_lifecycle(server_name),
                name=f"mcp.lifecycle.{server_name}",
            )
            connection.connection_task = connection_task

            # Wait for connection to establish with proper timeout
            try:
                await asyncio.wait_for(
                    connection_event.wait(), timeout=server_def.timeout
                )
                # Event was set, but check if it was success or error
                current_status = self.get_server_status(server_name)
                return current_status == MCPServerStatus.CONNECTED
            except asyncio.CancelledError:
                await cancel_and_wait(connection_task)
                raise
            except asyncio.TimeoutError:
                # A lifecycle can time out before it reaches disconnect_event.
                # Letting it continue would make refresh and shutdown wait on a
                # task that they cannot signal, so a timeout is terminal.
                error_msg = (
                    f"Connection to {server_name} timed out after "
                    f"{server_def.timeout}s"
                )
                LOGGER.warning(error_msg)
                self._update_server_status(
                    server_name, MCPServerStatus.ERROR, error_msg
                )
                await cancel_and_wait(connection_task)
                return False

        except Exception as e:
            error_msg = f"Failed to connect to MCP server {server_name} (transport: {server_def.transport}): {e!s}"
            LOGGER.error(error_msg)
            if server_name in self.connections:
                self._update_server_status(
                    server_name, MCPServerStatus.ERROR, error_msg
                )
            return False

    async def _discover_tools(self, connection: MCPServerConnection) -> None:
        """Discover tools from an MCP server."""
        LOGGER.info(
            f"Discovering tools for server: {connection.definition.name}"
        )

        if not connection.client:
            raise RuntimeError("No active client for tool discovery")

        tools: list[Tool] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()

        while True:
            tools_response: ListToolsResult = (
                await connection.client.list_tools(cursor=cursor)
            )
            tools.extend(tools_response.tools)
            cursor = tools_response.next_cursor
            if cursor is None:
                break
            if cursor in seen_cursors:
                raise RuntimeError(
                    f"Tool discovery returned repeated cursor {cursor!r}"
                )
            seen_cursors.add(cursor)

        self._remove_server_tools(connection.definition.name)
        self._add_server_tools(connection, tools)

        LOGGER.info(
            f"Discovered {len(connection.tools)} tools from {connection.definition.name}"
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
        """Connect to all configured MCP servers.

        Returns:
            Dictionary mapping server names to connection success status
        """
        results: dict[str, bool] = {}

        # Connect to servers concurrently
        tasks = [
            self.connect_to_server(server_name) for server_name in self.servers
        ]

        connection_results = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        for server_name, result in zip(
            self.servers.keys(), connection_results, strict=False
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
            CallToolResult with `is_error=True` and the error message.
        """
        # Based on the MCP SDK error handling:
        # https://modelcontextprotocol.io/docs/concepts/tools#error-handling
        from mcp.types import CallToolResult, TextContent

        return CallToolResult(
            is_error=True,
            content=[TextContent(type="text", text=error_message)],
        )

    def is_error_result(self, result: CallToolResult) -> bool:
        """Check if a CallToolResult represents an error."""
        return result.is_error is True

    async def invoke_tool(
        self,
        namespaced_tool_name: str,
        params: CallToolRequestParams,
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
        server_name = _get_metadata(tool).get("server_name")
        if not isinstance(server_name, str):
            return self._create_error_result(
                f"Internal error: Tool '{namespaced_tool_name}' missing server information"
            )

        if self.get_server_status(server_name) != MCPServerStatus.CONNECTED:
            return self._create_error_result(
                f"Server '{server_name}' is not connected"
            )

        connection = self.connections.get(server_name)
        if not connection or not connection.client:
            return self._create_error_result(
                f"Internal error: No active client for server '{server_name}'"
            )

        try:
            LOGGER.debug(
                f"Invoking MCP tool with params: {namespaced_tool_name}"
            )

            # Use asyncio.wait_for for timeout handling
            timeout = connection.definition.timeout
            result = await asyncio.wait_for(
                connection.client.call_tool(params.name, params.arguments),
                timeout=timeout,
            )

            # Validate the result
            if not result:
                LOGGER.warning(
                    f"Tool {namespaced_tool_name} returned empty result"
                )
                return self._create_error_result("Tool returned empty result")

            # Return the MCP SDK result directly (may already be an error).
            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool {namespaced_tool_name} timed out after {connection.definition.timeout} seconds"
            LOGGER.error(error_msg)

            return self._create_error_result(
                f"Tool execution timed out after {connection.definition.timeout} seconds"
            )

        except Exception as e:
            LOGGER.error(
                f"Failed to invoke tool {namespaced_tool_name} with params: {e!s}"
            )

            return self._create_error_result(f"Tool execution failed: {e!s}")

    def create_tool_params(
        self,
        namespaced_tool_name: str,
        arguments: MCPToolArgs = None,
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
        if result.is_error:
            LOGGER.debug(
                f"Extracted text content from error result: {len(text_contents)} items"
            )

        return text_contents

    def convert_tool_result(self, result: CallToolResult) -> object | None:
        """Convert an MCP result into a JSON-serializable tool output.

        Structured content is the most useful representation for an AI model.
        Text-only results retain the existing string shape. Mixed or non-text
        content keeps every MCP content block instead of silently dropping it.
        """
        structured_content = _get_structured_content(result)
        if structured_content is not None:
            return structured_content

        if not result.content:
            return None

        from mcp.types import TextContent

        text_content = [
            item for item in result.content if isinstance(item, TextContent)
        ]
        if len(text_content) == len(result.content):
            return " ".join(item.text for item in text_content)

        return {
            "content": [
                item.model_dump(by_alias=True, mode="json", exclude_none=True)
                for item in result.content
            ]
        }

    def format_tool_error(self, result: CallToolResult) -> str:
        """Convert an MCP error result into a stable message."""
        import json

        converted = self.convert_tool_result(result)
        if converted is None:
            return "Unknown MCP tool error"
        if isinstance(converted, str):
            return converted
        try:
            return json.dumps(converted, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(converted)

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

    def get_server_status(self, server_name: str) -> MCPServerStatus | None:
        """Get the status of a specific server."""
        connection = self.connections.get(server_name)
        return connection.status if connection else None

    def get_all_server_statuses(self) -> dict[str, MCPServerStatus]:
        """Get the status of all servers."""
        return {name: conn.status for name, conn in self.connections.items()}

    async def _monitor_server_health(self, server_name: str) -> None:
        """Continuously monitor server health."""
        consecutive_failures = 0
        try:
            while (
                self.get_server_status(server_name)
                == MCPServerStatus.CONNECTED
            ):
                try:
                    await asyncio.sleep(self.health_check_interval)
                    if (
                        self.get_server_status(server_name)
                        != MCPServerStatus.CONNECTED
                    ):
                        break

                    # Perform health check
                    health_check_passed = await self._perform_health_check(
                        server_name
                    )

                    if health_check_passed:
                        consecutive_failures = 0
                        # Handle successful health check
                        LOGGER.debug(f"Health check passed for {server_name}")
                        connection = self.connections.get(server_name)
                        if connection:
                            # Update last health check time
                            connection.last_health_check = time.time()
                    else:
                        consecutive_failures += 1
                        LOGGER.warning(
                            "Health check failed for %s (%d/%d)",
                            server_name,
                            consecutive_failures,
                            self.health_check_failure_threshold,
                        )

                        if (
                            consecutive_failures
                            < self.health_check_failure_threshold
                        ):
                            continue

                        # Determine the appropriate error message based on connection state
                        connection = self.connections.get(server_name)
                        if connection and not connection.client:
                            error_msg = "No active client"
                        else:
                            error_msg = "Health check failed"

                        # Update server status and remove tools
                        self._update_server_status(
                            server_name, MCPServerStatus.ERROR, error_msg
                        )
                        self._remove_server_tools(server_name)
                        if connection and connection.disconnect_event:
                            connection.disconnect_event.set()
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
            current_task = asyncio.current_task()
            if self.health_check_tasks.get(server_name) is current_task:
                self.health_check_tasks.pop(server_name, None)
                LOGGER.debug(
                    f"Removed health monitoring task for {server_name}"
                )

    async def _perform_health_check(self, server_name: str) -> bool:
        """Perform health check for a server and update its status"""
        connection = self.connections.get(server_name)
        if not connection:
            return False

        try:
            if not connection.client:
                return False

            await asyncio.wait_for(
                connection.client.list_tools(cache_mode="refresh"),
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
        error_message: str | None = None,
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
        server_name = connection.definition.name

        for tool in tools:
            namespaced_name = self._create_namespaced_tool_name(
                server_name, tool.name
            )

            # Keep the complete tool definition while attaching routing metadata.
            metadata = _get_metadata(tool)
            metadata.update(
                server_name=server_name,
                namespaced_name=namespaced_name,
            )
            mcp_tool = tool.model_copy(update={"meta": metadata})

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
        self, server_name: str | None = None
    ) -> None:
        """Cancel health monitoring for a specific server or all servers.

        Args:
            server_name: Server name to cancel monitoring for. If None, cancels all.
        """
        if server_name is not None:
            task = self.health_check_tasks.pop(server_name, None)
            if task:
                await cancel_and_wait(task)
                LOGGER.debug(f"Cancelled health monitoring for {server_name}")
        else:
            tasks = list(self.health_check_tasks.values())
            self.health_check_tasks.clear()
            if tasks:
                for task in tasks:
                    task.cancel()

                await asyncio.gather(
                    *tasks,
                    return_exceptions=True,
                )
                LOGGER.debug("Cancelled all health monitoring tasks")

    async def disconnect_from_server(self, server_name: str) -> bool:
        """Disconnect from a specific MCP server.

        Args:
            server_name: Name of the server to disconnect from

        Returns:
            True if disconnection was successful or server wasn't connected, False otherwise
        """
        connection = self.connections.get(server_name)
        if not connection:
            return True

        try:
            # Signal the connection task to shutdown
            if connection.disconnect_event:
                connection.disconnect_event.set()

            # Wait for the connection task to complete its cleanup
            if connection.connection_task:
                try:
                    await asyncio.shield(connection.connection_task)
                except asyncio.CancelledError:
                    if not connection.connection_task.cancelled():
                        raise

            LOGGER.info(f"Disconnected from MCP server: {server_name}")
            return True

        except Exception as e:
            # No retry or forced cleanup - disconnection failures are logged but not blocking.
            # Local state cleanup happens in _connection_lifecycle finally block regardless.
            LOGGER.error(
                f"Error disconnecting from server {server_name}: {e!s}"
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
_mcp_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance, initializing it if needed.

    Note: The client must be configured using await client.configure(config)
          before connecting to servers.
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
        LOGGER.info("MCP client initialized")
    return _mcp_client
