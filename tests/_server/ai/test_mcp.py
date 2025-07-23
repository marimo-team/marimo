# Copyright 2024 Marimo. All rights reserved.
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from marimo._config.config import (
    MCPConfig,
    MCPServerStdioConfig,
    MCPServerStreamableHttpConfig,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.mcp import (
    MCPClient,
    MCPServerConnection,
    MCPServerDefinition,
    MCPServerDefinitionFactory,
    MCPServerStatus,
    MCPTransportRegistry,
    MCPTransportType,
    StdioTransportConnector,
    StreamableHTTPTransportConnector,
    get_mcp_client,
)

# test fixtures and helpers


@pytest.fixture
def mock_session_setup():
    """Create a properly configured mock session with async context manager behavior."""

    def _create_mock_session(additional_methods=None, side_effects=None):
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock()
        mock_session.list_tools.return_value.tools = []

        # Add any additional methods specified
        if additional_methods:
            for method_name, method_mock in additional_methods.items():
                setattr(mock_session, method_name, method_mock)

        # Apply any side effects
        if side_effects:
            for method_name, side_effect in side_effects.items():
                getattr(mock_session, method_name).side_effect = side_effect

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        return mock_session, mock_session_context

    return _create_mock_session


@pytest.fixture
def mock_stdio_setup():
    """Create a properly configured mock stdio client with async context manager behavior."""

    def _create_mock_stdio():
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio_context = AsyncMock()
        mock_stdio_context.__aenter__ = AsyncMock(
            return_value=(mock_read, mock_write)
        )
        mock_stdio_context.__aexit__ = AsyncMock(return_value=None)

        return mock_read, mock_write, mock_stdio_context

    return _create_mock_stdio


def create_test_server_definition(
    name: str = "test_server",
    command: str = "test",
    args: list = None,
    env: dict = None,
    timeout: float = None,
) -> MCPServerDefinition:
    """Create a test server definition with sensible defaults."""
    if args is None:
        args = []
    if env is None:
        env = {}

    config = MCPServerStdioConfig(command=command, args=args, env=env)
    server_def = MCPServerDefinitionFactory.from_config(name, config)

    if timeout is not None:
        server_def.timeout = timeout

    return server_def


def create_test_server_connection(
    name: str = "test_server",
    command: str = "test",
    args: list = None,
    env: dict = None,
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED,
    session=None,
    timeout: float = None,
) -> MCPServerConnection:
    """Create a test server connection with sensible defaults."""
    server_def = create_test_server_definition(
        name, command, args, env, timeout
    )
    connection = MCPServerConnection(definition=server_def)
    connection.status = status
    connection.session = session
    return connection


def create_test_tool(
    name: str = "test_tool",
    description: str = "Test tool",
    server_name: str = "test_server",
    namespaced_name: str = None,
    input_schema: dict = None,
):
    """Create a test tool with sensible defaults."""
    if DependencyManager.mcp.has():
        from mcp.types import Tool

        if input_schema is None:
            input_schema = {"type": "object"}
        if namespaced_name is None:
            namespaced_name = f"mcp_{server_name}_{name}"

        return Tool(
            name=name,
            description=description,
            inputSchema=input_schema,
            _meta={
                "server_name": server_name,
                "namespaced_name": namespaced_name,
            },
        )
    return None


# tests


class TestMCPServerDefinition:
    """Test cases for MCPServerDefinition class."""

    @pytest.mark.parametrize(
        ("config_type", "expected_transport", "config_kwargs"),
        [
            pytest.param(
                MCPServerStdioConfig,
                MCPTransportType.STDIO,
                {
                    "command": "python",
                    "args": ["server.py"],
                    "env": {"API_KEY": "test"},
                },
                id="stdio_transport",
            ),
            pytest.param(
                MCPServerStreamableHttpConfig,
                MCPTransportType.STREAMABLE_HTTP,
                {
                    "url": "https://api.example.com/mcp",
                    "headers": {"Auth": "Bearer token"},
                    "timeout": 45.0,
                },
                id="http_transport",
            ),
        ],
    )
    def test_from_config_transport_detection(
        self, config_type, expected_transport, config_kwargs
    ):
        """Test that transport types are correctly auto-detected from configuration."""
        config = config_type(**config_kwargs)
        server_def = MCPServerDefinitionFactory.from_config(
            "test_server", config
        )

        assert server_def.name == "test_server"
        assert server_def.transport == expected_transport
        assert server_def.config == config

        # Verify transport-specific attributes are available from config
        if expected_transport == MCPTransportType.STDIO:
            assert server_def.config.command == config_kwargs["command"]
            assert server_def.config.args == config_kwargs["args"]
            assert server_def.config.env == config_kwargs["env"]
        elif expected_transport == MCPTransportType.STREAMABLE_HTTP:
            assert server_def.config.url == config_kwargs["url"]
            assert server_def.config.headers == config_kwargs["headers"]
            assert server_def.timeout == config_kwargs["timeout"]


class TestMCPTransportConnectors:
    """Test cases for transport connector classes."""

    def test_transport_registry_functionality(self):
        """Test that the transport registry properly handles all transport types."""
        registry = MCPTransportRegistry()

        # Test that all transport types are supported
        for transport_type in MCPTransportType:
            connector = registry.get_connector(transport_type)
            assert connector is not None

        # Test unsupported transport type
        with pytest.raises(ValueError, match="Unsupported transport type"):
            registry.get_connector("unsupported_transport")  # type: ignore

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    @patch("mcp.client.stdio.stdio_client")
    async def test_stdio_connector_connect(self, mock_stdio_client):
        """Test STDIO transport connector connection."""
        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(
            return_value=(mock_read, mock_write)
        )
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stdio_client.return_value = mock_context

        # Create connector and test connection
        connector = StdioTransportConnector()
        config = MCPServerStdioConfig(
            command="python", args=["server.py"], env={"TEST_VAR": "value"}
        )
        server_def = MCPServerDefinition(
            name="test", transport=MCPTransportType.STDIO, config=config
        )

        from contextlib import AsyncExitStack

        async with AsyncExitStack() as exit_stack:
            read, write = await connector.connect(server_def, exit_stack)
            assert read == mock_read
            assert write == mock_write

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    @patch("mcp.client.streamable_http.streamablehttp_client")
    async def test_http_connector_connect(self, mock_http_client):
        """Test HTTP transport connector connection."""
        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(
            return_value=(mock_read, mock_write)
        )
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_http_client.return_value = mock_context

        # Create connector and test connection
        connector = StreamableHTTPTransportConnector()
        config = MCPServerStreamableHttpConfig(
            url="https://api.example.com/mcp",
            headers={"Authorization": "Bearer token"},
            timeout=30.0,
        )
        server_def = MCPServerDefinition(
            name="test",
            transport=MCPTransportType.STREAMABLE_HTTP,
            config=config,
            timeout=30.0,
        )

        from contextlib import AsyncExitStack

        async with AsyncExitStack() as exit_stack:
            read, write = await connector.connect(server_def, exit_stack)
            assert read == mock_read
            assert write == mock_write


class TestMCPClientConfiguration:
    """Test cases for MCPClient configuration parsing and initialization."""

    def test_init_with_empty_config(self):
        """Test MCPClient initialization with empty config."""
        config = MCPConfig(mcpServers={})
        client = MCPClient(config)
        assert client.servers == {}
        assert client.connections == {}
        assert client.tool_registry == {}

    @pytest.mark.parametrize(
        ("server_configs", "expected_servers"),
        [
            pytest.param(
                {
                    "stdio_server": MCPServerStdioConfig(
                        command="python",
                        args=["test.py"],
                        env={"TEST": "value"},
                    ),
                },
                ["stdio_server"],
                id="single_stdio_server",
            ),
            pytest.param(
                {
                    "http_server": MCPServerStreamableHttpConfig(
                        url="https://api.example.com/mcp",
                        headers={"Auth": "Bearer token"},
                    ),
                },
                ["http_server"],
                id="single_http_server",
            ),
            pytest.param(
                {
                    "stdio_server": MCPServerStdioConfig(
                        command="python", args=["test.py"]
                    ),
                    "http_server": MCPServerStreamableHttpConfig(
                        url="https://api.example.com/mcp"
                    ),
                },
                ["stdio_server", "http_server"],
                id="mixed_servers",
            ),
        ],
    )
    def test_parse_config_valid_servers(
        self, server_configs, expected_servers
    ):
        """Test parsing valid server configurations."""
        config = MCPConfig(mcpServers=server_configs)
        client = MCPClient(config)

        assert len(client.servers) == len(expected_servers)
        for server_name in expected_servers:
            assert server_name in client.servers
            server_def = client.servers[server_name]
            assert server_def.name == server_name


class TestMCPClientToolManagement:
    """Test cases for MCPClient tool management functionality."""

    def test_create_namespaced_tool_name_no_conflict(self):
        """Test creating namespaced tool name without conflicts."""
        client = MCPClient(MCPConfig(mcpServers={}))
        name = client._create_namespaced_tool_name("github", "create_issue")
        assert name == "mcp_github_create_issue"

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    def test_create_namespaced_tool_name_with_conflicts(self):
        """Test creating namespaced tool name with conflicts and counter resolution."""
        client = MCPClient(MCPConfig(mcpServers={}))

        from mcp.types import Tool

        # Create first tool - should get base name
        name1 = client._create_namespaced_tool_name("github", "create_issue")
        assert name1 == "mcp_github_create_issue"

        # Add it to registry
        tool1 = Tool(
            name="create_issue",
            description="Test tool",
            inputSchema={},
            _meta={"server_name": "github", "namespaced_name": name1},
        )
        client.tool_registry[name1] = tool1

        # Create second tool with same name - should get numbered suffix
        name2 = client._create_namespaced_tool_name("github", "create_issue")
        assert name2 == "mcp_github1_create_issue"

        # Create third tool - should get next counter
        name3 = client._create_namespaced_tool_name("github", "create_issue")
        assert name3 == "mcp_github2_create_issue"

        # All names should be unique
        assert len({name1, name2, name3}) == 3

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    def test_add_server_tools(self):
        """Test adding tools from a server to registry and connection."""
        client = MCPClient(MCPConfig(mcpServers={}))
        from mcp.types import Tool

        # Create server connection
        connection = create_test_server_connection()

        # Create raw tools to add
        raw_tools = [
            Tool(
                name="tool1",
                description="Test tool 1",
                inputSchema={"type": "object"},
            ),
            Tool(
                name="tool2",
                description="Test tool 2",
                inputSchema={"type": "object"},
            ),
        ]

        # Add tools
        client._add_server_tools(connection, raw_tools)

        # Verify tools are added to connection
        assert len(connection.tools) == 2

        # Verify tools are added to registry with proper namespacing
        assert "mcp_test_server_tool1" in client.tool_registry
        assert "mcp_test_server_tool2" in client.tool_registry

        # Verify tool metadata
        tool1 = client.tool_registry["mcp_test_server_tool1"]
        assert tool1.meta["server_name"] == "test_server"
        assert tool1.meta["namespaced_name"] == "mcp_test_server_tool1"

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    def test_remove_server_tools(self):
        """Test removing tools from a server."""
        client = MCPClient(MCPConfig(mcpServers={}))
        from mcp.types import Tool

        # Create tools from different servers
        server1_tools = [
            (
                "mcp_server1_tool1",
                Tool(
                    name="tool1",
                    description="Test",
                    inputSchema={},
                    _meta={
                        "server_name": "server1",
                        "namespaced_name": "mcp_server1_tool1",
                    },
                ),
            ),
            (
                "mcp_server1_tool2",
                Tool(
                    name="tool2",
                    description="Test",
                    inputSchema={},
                    _meta={
                        "server_name": "server1",
                        "namespaced_name": "mcp_server1_tool2",
                    },
                ),
            ),
        ]
        server2_tools = [
            (
                "mcp_server2_tool3",
                Tool(
                    name="tool3",
                    description="Test",
                    inputSchema={},
                    _meta={
                        "server_name": "server2",
                        "namespaced_name": "mcp_server2_tool3",
                    },
                ),
            )
        ]

        # Add tools to registry
        for namespaced_name, tool in server1_tools + server2_tools:
            client.tool_registry[namespaced_name] = tool

        # Create connection and add tools
        connection = create_test_server_connection(name="server1")
        connection.tools = [tool for _, tool in server1_tools]
        client.connections["server1"] = connection

        # Set a counter for the server
        client.server_counters["server1"] = 3

        # Remove tools from server1
        client._remove_server_tools("server1")

        # Verify server1 tools are removed
        for namespaced_name, _ in server1_tools:
            assert namespaced_name not in client.tool_registry

        # Verify server2 tools remain
        for namespaced_name, _ in server2_tools:
            assert namespaced_name in client.tool_registry

        # Verify connection tools are cleared
        assert len(connection.tools) == 0

        # Verify counter is reset
        assert "server1" not in client.server_counters

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    @pytest.mark.parametrize(
        ("server_name", "expected_tool_count"),
        [
            pytest.param("server1", 2, id="existing_server"),
            pytest.param("nonexistent", 0, id="nonexistent_server"),
        ],
    )
    def test_get_tools_by_server(self, server_name, expected_tool_count):
        """Test getting tools by server name."""
        client = MCPClient(MCPConfig(mcpServers={}))
        from mcp.types import Tool

        # Add tools from different servers
        tools_data = [
            ("mcp_server1_tool1", "server1"),
            ("mcp_server1_tool2", "server1"),
            ("mcp_server2_tool3", "server2"),
        ]

        for namespaced_name, server in tools_data:
            tool = Tool(
                name=namespaced_name.split("_")[-1],
                description="Test",
                inputSchema={},
                _meta={
                    "server_name": server,
                    "namespaced_name": namespaced_name,
                },
            )
            client.tool_registry[namespaced_name] = tool

        # Get tools by server
        tools = client.get_tools_by_server(server_name)
        assert len(tools) == expected_tool_count


@pytest.mark.skipif(
    not DependencyManager.mcp.has(), reason="MCP SDK not available"
)
class TestMCPClientToolExecution:
    """Test cases for MCPClient tool execution functionality."""

    def test_create_tool_params(self):
        """Test creating properly typed CallToolRequestParams."""
        client = MCPClient(MCPConfig(mcpServers={}))

        # Add a mock tool to the registry
        mock_tool = create_test_tool()
        client.tool_registry["mcp_test_server_test_tool"] = mock_tool

        # Test creating tool params with arguments
        params = client.create_tool_params(
            "mcp_test_server_test_tool", {"arg1": "value1"}
        )
        assert params.name == "test_tool"
        assert params.arguments == {"arg1": "value1"}

        # Test with no arguments
        params_no_args = client.create_tool_params("mcp_test_server_test_tool")
        assert params_no_args.name == "test_tool"
        assert params_no_args.arguments is None

        # Test with non-existent tool
        with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
            client.create_tool_params("nonexistent")

    @pytest.mark.parametrize(
        ("tool_setup", "connection_setup", "expected_error_pattern"),
        [
            pytest.param(
                None,  # No tool setup
                {"status": MCPServerStatus.CONNECTED, "session": AsyncMock()},
                "Tool 'nonexistent_tool' not found",
                id="tool_not_found",
            ),
            pytest.param(
                {"server_name": "test_server"},
                {"status": MCPServerStatus.DISCONNECTED, "session": None},
                "Server 'test_server' is not connected",
                id="server_not_connected",
            ),
            pytest.param(
                {"server_name": "test_server"},
                {"status": MCPServerStatus.CONNECTED, "session": None},
                "No active session for server 'test_server'",
                id="no_active_session",
            ),
        ],
    )
    async def test_invoke_tool_error_cases(
        self, tool_setup, connection_setup, expected_error_pattern
    ):
        """Test invoke_tool error handling scenarios."""
        client = MCPClient(MCPConfig(mcpServers={}))
        from mcp.types import Tool

        # Setup tool if provided
        if tool_setup:
            mock_tool = Tool(
                name="test_tool",
                description="Test tool",
                inputSchema={},
                _meta={
                    "server_name": tool_setup["server_name"],
                    "namespaced_name": "mcp_test_server_test_tool",
                },
            )
            client.tool_registry["mcp_test_server_test_tool"] = mock_tool

            # Setup connection
            server_def = MCPServerDefinitionFactory.from_config(
                "test_server", MCPServerStdioConfig(command="test", args=[])
            )
            connection = MCPServerConnection(definition=server_def)
            connection.status = connection_setup["status"]
            connection.session = connection_setup["session"]
            client.connections["test_server"] = connection

            # Create params for the tool
            params = client.create_tool_params(
                "mcp_test_server_test_tool", {"arg1": "value1"}
            )
            tool_name = "mcp_test_server_test_tool"
        else:
            # Use non-existent tool
            from mcp.types import CallToolRequestParams

            params = CallToolRequestParams(
                name="nonexistent", arguments={"arg1": "value1"}
            )
            tool_name = "nonexistent_tool"

        # Test tool invocation
        result = await client.invoke_tool(tool_name, params)

        # Verify it's an error result
        assert client.is_error_result(result) is True

        # Verify error message
        error_messages = client.extract_text_content(result)
        assert len(error_messages) > 0
        assert expected_error_pattern in error_messages[0]

    async def test_invoke_tool_success(self):
        """Test successful tool invocation."""
        client = MCPClient(MCPConfig(mcpServers={}))
        from mcp.types import CallToolResult, TextContent

        # Setup tool
        mock_tool = create_test_tool()
        client.tool_registry["mcp_test_server_test_tool"] = mock_tool

        # Setup connection with mock session
        connection = create_test_server_connection(
            status=MCPServerStatus.CONNECTED, session=AsyncMock()
        )

        # Mock successful tool result
        expected_result = CallToolResult(
            content=[
                TextContent(type="text", text="Tool executed successfully")
            ]
        )
        connection.session.call_tool = AsyncMock(return_value=expected_result)
        client.connections["test_server"] = connection

        # Create params and invoke tool
        params = client.create_tool_params(
            "mcp_test_server_test_tool", {"arg1": "value1"}
        )
        result = await client.invoke_tool("mcp_test_server_test_tool", params)

        # Verify result
        assert client.is_error_result(result) is False
        text_contents = client.extract_text_content(result)
        assert "Tool executed successfully" in text_contents[0]

        # Verify session was called correctly
        connection.session.call_tool.assert_called_once_with(
            "test_tool", {"arg1": "value1"}
        )

    async def test_invoke_tool_timeout(self):
        """Test tool invocation timeout handling."""
        client = MCPClient(MCPConfig(mcpServers={}))

        # Setup tool
        mock_tool = create_test_tool()
        client.tool_registry["mcp_test_server_test_tool"] = mock_tool

        # Setup connection with timeout
        connection = create_test_server_connection(
            timeout=0.1,  # Very short timeout
            status=MCPServerStatus.CONNECTED,
            session=AsyncMock(),
        )

        # Mock session to hang longer than timeout
        async def slow_call_tool(_name, _args):
            await asyncio.sleep(1)  # Longer than timeout

        connection.session.call_tool = AsyncMock(side_effect=slow_call_tool)
        client.connections["test_server"] = connection

        # Create params and invoke tool
        params = client.create_tool_params(
            "mcp_test_server_test_tool", {"arg1": "value1"}
        )
        result = await client.invoke_tool("mcp_test_server_test_tool", params)

        # Verify timeout error
        assert client.is_error_result(result) is True
        error_messages = client.extract_text_content(result)
        assert "timed out" in error_messages[0]

    @pytest.mark.parametrize(
        ("result_content", "expected_is_error", "expected_text_count"),
        [
            pytest.param(
                [{"type": "text", "text": "Success message"}],
                False,
                1,
                id="success_result",
            ),
            pytest.param(
                [{"type": "text", "text": "Error occurred"}],
                True,
                1,
                id="error_result",
            ),
            pytest.param(
                [
                    {"type": "text", "text": "First message"},
                    {"type": "text", "text": "Second message"},
                ],
                False,
                2,
                id="multiple_text_content",
            ),
        ],
    )
    def test_result_handling_helpers(
        self, result_content, expected_is_error, expected_text_count
    ):
        """Test CallToolResult helper methods."""
        from mcp.types import CallToolResult, TextContent

        client = MCPClient(MCPConfig(mcpServers={}))

        # Create result
        content = [TextContent(**item) for item in result_content]
        result = CallToolResult(isError=expected_is_error, content=content)

        # Test error detection
        assert client.is_error_result(result) == expected_is_error

        # Test text extraction
        text_contents = client.extract_text_content(result)
        assert len(text_contents) == expected_text_count

        for i, expected_text in enumerate(
            [item["text"] for item in result_content]
        ):
            assert text_contents[i] == expected_text


@pytest.mark.skipif(
    not DependencyManager.mcp.has(), reason="MCP SDK not available"
)
class TestMCPClientConnectionManagement:
    """Test cases for MCPClient connection management functionality."""

    async def test_discover_tools_success(self):
        """Test successful tool discovery from an MCP server."""
        client = MCPClient(MCPConfig(mcpServers={}))
        from mcp.types import ListToolsResult, Tool

        # Create mock connection with session
        mock_session = AsyncMock()
        connection = create_test_server_connection(session=mock_session)

        # Mock tools response
        mock_tools = [
            Tool(
                name="tool1",
                description="First tool",
                inputSchema={"type": "object"},
            ),
            Tool(
                name="tool2",
                description="Second tool",
                inputSchema={"type": "object"},
            ),
        ]
        mock_response = ListToolsResult(tools=mock_tools)
        mock_session.list_tools = AsyncMock(return_value=mock_response)

        # Test tool discovery
        await client._discover_tools(connection)

        # Verify tools were added
        assert len(connection.tools) == 2
        assert "mcp_test_server_tool1" in client.tool_registry
        assert "mcp_test_server_tool2" in client.tool_registry

        # Verify session was called
        mock_session.list_tools.assert_called_once()

    async def test_discover_tools_no_session(self):
        """Test tool discovery with no active session."""
        client = MCPClient(MCPConfig(mcpServers={}))

        # Create connection without session
        connection = create_test_server_connection(session=None)

        # Test tool discovery (should handle gracefully)
        await client._discover_tools(connection)

        # Verify no tools were added
        assert len(connection.tools) == 0
        assert len(client.tool_registry) == 0

    @patch("mcp.ClientSession")
    @patch("mcp.client.stdio.stdio_client")
    async def test_connect_to_server_success(
        self,
        mock_stdio_client,
        mock_session_class,
        mock_stdio_setup,
        mock_session_setup,
    ):
        """Test successful server connection with complete flow."""
        # Setup stdio and session mocks using fixtures
        mock_read, mock_write, mock_stdio_context = mock_stdio_setup()
        mock_stdio_client.return_value = mock_stdio_context

        mock_session, mock_session_context = mock_session_setup()
        mock_session_class.return_value = mock_session_context

        # Mock AsyncExitStack
        with patch(
            "marimo._server.ai.mcp.AsyncExitStack"
        ) as mock_exit_stack_class:
            mock_exit_stack = AsyncMock()
            mock_exit_stack.enter_async_context = AsyncMock()
            mock_exit_stack.enter_async_context.side_effect = [
                (mock_read, mock_write),  # First call for stdio_client
                mock_session,  # Second call for ClientSession
            ]
            mock_exit_stack_class.return_value = mock_exit_stack

            # Create client with test config
            config = MCPConfig(
                mcpServers={
                    "test_server": MCPServerStdioConfig(
                        command="python", args=["test.py"], env={}
                    )
                }
            )
            client = MCPClient(config)

            # Test connection
            result = await client.connect_to_server("test_server")

            assert result is True
            assert "test_server" in client.connections
            assert (
                client.connections["test_server"].status
                == MCPServerStatus.CONNECTED
            )

    @pytest.mark.parametrize(
        ("server_exists", "already_connected", "expected_result"),
        [
            pytest.param(False, False, False, id="server_not_found"),
            pytest.param(True, True, True, id="already_connected"),
        ],
    )
    async def test_connect_to_server_edge_cases(
        self, server_exists, already_connected, expected_result
    ):
        """Test server connection edge cases."""
        config = MCPConfig(mcpServers={})
        if server_exists:
            config.mcpServers["test_server"] = MCPServerStdioConfig(
                command="python", args=["test.py"]
            )

        client = MCPClient(config)

        if already_connected:
            # Setup existing connection
            server_def = MCPServerDefinitionFactory.from_config(
                "test_server", MCPServerStdioConfig(command="test", args=[])
            )
            connection = MCPServerConnection(definition=server_def)
            connection.status = MCPServerStatus.CONNECTED
            client.connections["test_server"] = connection

        result = await client.connect_to_server("test_server")
        assert result == expected_result

    @patch("mcp.ClientSession")
    async def test_connect_to_all_servers_mixed_results(
        self, mock_session_class
    ):
        """Test connecting to multiple servers with mixed success/failure."""
        # Setup session mock for successful connections
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock()
        mock_session.list_tools.return_value.tools = []

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_context

        with patch(
            "marimo._server.ai.mcp.AsyncExitStack"
        ) as mock_exit_stack_class:
            mock_exit_stack = AsyncMock()
            mock_exit_stack.enter_async_context = AsyncMock()
            # Simulate success for server1, failure for server2
            mock_exit_stack.enter_async_context.side_effect = [
                (AsyncMock(), AsyncMock()),  # server1 stdio success
                mock_session,  # server1 session success
                Exception("Connection failed"),  # server2 failure
            ]
            mock_exit_stack_class.return_value = mock_exit_stack

            with patch("mcp.client.stdio.stdio_client") as mock_stdio_client:
                mock_stdio_context = AsyncMock()
                mock_stdio_context.__aenter__ = AsyncMock(
                    return_value=(AsyncMock(), AsyncMock())
                )
                mock_stdio_context.__aexit__ = AsyncMock(return_value=None)
                mock_stdio_client.return_value = mock_stdio_context

                config = MCPConfig(
                    mcpServers={
                        "server1": MCPServerStdioConfig(
                            command="python", args=["test1.py"]
                        ),
                        "server2": MCPServerStdioConfig(
                            command="python", args=["test2.py"]
                        ),
                    }
                )
                client = MCPClient(config)

                results = await client.connect_to_all_servers()

                # Verify mixed results
                assert len(results) == 2
                assert results["server1"] is True
                assert results["server2"] is False


class TestMCPClientHealthMonitoring:
    """Test cases for MCPClient health monitoring functionality."""

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    async def test_perform_health_check_success(self):
        """Test successful health check."""
        client = MCPClient(MCPConfig(mcpServers={}))

        # Create connection with mock session
        server_def = MCPServerDefinitionFactory.from_config(
            "test", MCPServerStdioConfig(command="test", args=[])
        )
        connection = MCPServerConnection(definition=server_def)
        connection.session = AsyncMock()
        connection.session.send_ping = AsyncMock()
        client.connections["test"] = connection

        result = await client._perform_health_check("test")

        assert result is True
        connection.session.send_ping.assert_called_once()
        # Note: last_health_check is updated by the caller (_monitor_server_health), not _perform_health_check
        assert connection.last_health_check == 0  # Should remain unchanged

    @pytest.mark.parametrize(
        ("session_setup", "ping_behavior", "expected_result"),
        [
            pytest.param(
                None,  # No session
                None,
                False,
                id="no_session",
            ),
            pytest.param(
                AsyncMock(),  # Valid session
                Exception("Ping failed"),  # Exception during ping
                False,
                id="ping_exception",
            ),
        ],
    )
    async def test_perform_health_check_failure_cases(
        self, session_setup, ping_behavior, expected_result
    ):
        """Test health check failure scenarios."""
        client = MCPClient(MCPConfig(mcpServers={}))

        # Create connection
        server_def = MCPServerDefinitionFactory.from_config(
            "test", MCPServerStdioConfig(command="test", args=[])
        )
        connection = MCPServerConnection(definition=server_def)
        connection.session = session_setup

        if session_setup and ping_behavior:
            connection.session.send_ping = AsyncMock(side_effect=ping_behavior)

        client.connections["test"] = connection

        result = await client._perform_health_check("test")

        assert result == expected_result
        # Note: _perform_health_check doesn't update connection status directly
        # Status updates happen in the calling code (_monitor_server_health)

    async def test_perform_health_check_timeout(self):
        """Test health check timeout handling."""
        client = MCPClient(MCPConfig(mcpServers={}))
        client.health_check_timeout = 0.1  # Very short timeout

        # Create connection with session that hangs
        server_def = MCPServerDefinitionFactory.from_config(
            "test", MCPServerStdioConfig(command="test", args=[])
        )
        connection = MCPServerConnection(definition=server_def)
        connection.session = AsyncMock()

        # Create a coroutine that sleeps longer than timeout
        async def slow_ping():
            await asyncio.sleep(1)

        connection.session.send_ping = AsyncMock(side_effect=slow_ping)
        client.connections["test"] = connection

        result = await client._perform_health_check("test")

        assert result is False
        # Note: _perform_health_check doesn't update connection status directly
        # Status updates happen in the calling code (_monitor_server_health)


class TestMCPServerConnection:
    """Test cases for MCPServerConnection class."""

    def test_server_connection_creation(self):
        """Test creating a server connection with proper defaults."""
        server_def = MCPServerDefinitionFactory.from_config(
            "test_server",
            MCPServerStdioConfig(
                command="python", args=["test.py"], env={"TEST": "value"}
            ),
        )

        connection = MCPServerConnection(definition=server_def)

        assert connection.definition.name == "test_server"
        assert connection.definition.config.command == "python"
        assert connection.definition.config.args == ["test.py"]
        assert connection.definition.config.env == {"TEST": "value"}
        assert connection.status == MCPServerStatus.DISCONNECTED
        assert connection.session is None
        assert len(connection.tools) == 0
        assert connection.last_health_check == 0
        assert connection.error_message is None


class TestMCPUtilities:
    """Test utility functions and configuration."""

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    def test_get_mcp_client_singleton(self):
        """Test that get_mcp_client returns singleton instance."""
        client1 = get_mcp_client()
        client2 = get_mcp_client()

        assert client1 is client2

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    def test_get_mcp_client_with_custom_config(self):
        """Test get_mcp_client with custom configuration."""
        # Reset global client for this test
        import marimo._server.ai.mcp as mcp_module

        mcp_module._MCP_CLIENT = None

        custom_config = MCPConfig(
            mcpServers={
                "custom_server": MCPServerStdioConfig(
                    command="custom", args=["--test"], env={}
                )
            }
        )

        client = get_mcp_client(custom_config)
        assert "custom_server" in client.servers
