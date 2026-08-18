# Copyright 2026 Marimo. All rights reserved.
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
    MCP_PRESETS,
    MCPClient,
    MCPConfigComparator,
    MCPServerConnection,
    MCPServerDefinition,
    MCPServerDefinitionFactory,
    MCPServerStatus,
    MCPTransportRegistry,
    MCPTransportType,
    StdioTransportConnector,
    StreamableHTTPTransportConnector,
    append_presets,
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
    args: list | None = None,
    env: dict | None = None,
    timeout: float | None = None,
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
    args: list | None = None,
    env: dict | None = None,
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED,
    client=None,
    timeout: float | None = None,
) -> MCPServerConnection:
    """Create a test server connection with sensible defaults."""
    server_def = create_test_server_definition(
        name, command, args, env, timeout
    )
    connection = MCPServerConnection(definition=server_def)
    connection.status = status
    connection.client = client
    return connection


def create_test_tool(
    name: str = "test_tool",
    description: str = "Test tool",
    server_name: str = "test_server",
    namespaced_name: str | None = None,
    input_schema: dict | None = None,
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
            input_schema=input_schema,
            _meta={
                "server_name": server_name,
                "namespaced_name": namespaced_name,
            },
        )
    return None


def create_connection_task(
    error: Exception | None = None,
) -> asyncio.Task[None]:
    async def lifecycle() -> None:
        if error is not None:
            raise error

    return asyncio.create_task(lifecycle())


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
            assert server_def.config["command"] == config_kwargs["command"]
            assert server_def.config.get("args") == config_kwargs["args"]
            assert server_def.config.get("env") == config_kwargs["env"]
        elif expected_transport == MCPTransportType.STREAMABLE_HTTP:
            assert server_def.config["url"] == config_kwargs["url"]
            assert server_def.config.get("headers") == config_kwargs["headers"]
            assert server_def.timeout == config_kwargs["timeout"]


class TestMCPConfigComparator:
    """Test cases for MCPConfigComparator utility class."""

    def test_compute_diff_no_changes(self):
        """Test that compute_diff detects no changes when configs are identical."""
        server1 = MCPServerDefinition(
            name="server1",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test", args=[], env={}),
            timeout=30.0,
        )

        current = {"server1": server1}
        new = {"server1": server1}

        diff = MCPConfigComparator.compute_diff(current, new)

        assert not diff.has_changes()
        assert len(diff.servers_to_add) == 0
        assert len(diff.servers_to_remove) == 0
        assert len(diff.servers_to_update) == 0
        assert "server1" in diff.servers_unchanged

    def test_compute_diff_add_servers(self):
        """Test that compute_diff detects new servers."""
        server1 = MCPServerDefinition(
            name="server1",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test1", args=[], env={}),
            timeout=30.0,
        )
        server2 = MCPServerDefinition(
            name="server2",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test2", args=[], env={}),
            timeout=30.0,
        )

        current = {"server1": server1}
        new = {"server1": server1, "server2": server2}

        diff = MCPConfigComparator.compute_diff(current, new)

        assert diff.has_changes()
        assert "server2" in diff.servers_to_add
        assert len(diff.servers_to_remove) == 0
        assert len(diff.servers_to_update) == 0
        assert "server1" in diff.servers_unchanged

    def test_compute_diff_remove_servers(self):
        """Test that compute_diff detects removed servers."""
        server1 = MCPServerDefinition(
            name="server1",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test1", args=[], env={}),
            timeout=30.0,
        )
        server2 = MCPServerDefinition(
            name="server2",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test2", args=[], env={}),
            timeout=30.0,
        )

        current = {"server1": server1, "server2": server2}
        new = {"server1": server1}

        diff = MCPConfigComparator.compute_diff(current, new)

        assert diff.has_changes()
        assert "server2" in diff.servers_to_remove
        assert len(diff.servers_to_add) == 0
        assert len(diff.servers_to_update) == 0
        assert "server1" in diff.servers_unchanged

    def test_compute_diff_update_servers(self):
        """Test that compute_diff detects modified servers."""
        server1_old = MCPServerDefinition(
            name="server1",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(
                command="test", args=["--old"], env={}
            ),
            timeout=30.0,
        )
        server1_new = MCPServerDefinition(
            name="server1",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(
                command="test", args=["--new"], env={}
            ),
            timeout=30.0,
        )

        current = {"server1": server1_old}
        new = {"server1": server1_new}

        diff = MCPConfigComparator.compute_diff(current, new)

        assert diff.has_changes()
        assert "server1" in diff.servers_to_update
        assert len(diff.servers_to_add) == 0
        assert len(diff.servers_to_remove) == 0
        assert len(diff.servers_unchanged) == 0

    def test_compute_diff_mixed_changes(self):
        """Test compute_diff with multiple types of changes."""
        server1 = MCPServerDefinition(
            name="unchanged",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test1", args=[], env={}),
            timeout=30.0,
        )
        server2_old = MCPServerDefinition(
            name="updated",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(
                command="test2", args=["--old"], env={}
            ),
            timeout=30.0,
        )
        server2_new = MCPServerDefinition(
            name="updated",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(
                command="test2", args=["--new"], env={}
            ),
            timeout=30.0,
        )
        server3 = MCPServerDefinition(
            name="removed",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test3", args=[], env={}),
            timeout=30.0,
        )
        server4 = MCPServerDefinition(
            name="added",
            transport=MCPTransportType.STDIO,
            config=MCPServerStdioConfig(command="test4", args=[], env={}),
            timeout=30.0,
        )

        current = {
            "unchanged": server1,
            "updated": server2_old,
            "removed": server3,
        }
        new = {"unchanged": server1, "updated": server2_new, "added": server4}

        diff = MCPConfigComparator.compute_diff(current, new)

        assert diff.has_changes()
        assert "unchanged" in diff.servers_unchanged
        assert "updated" in diff.servers_to_update
        assert "removed" in diff.servers_to_remove
        assert "added" in diff.servers_to_add


class TestMCPPresets:
    """Test cases for MCP preset configuration system."""

    def test_preset_definitions_exist(self):
        """Test that expected presets are defined."""
        assert "marimo" in MCP_PRESETS
        assert "context7" in MCP_PRESETS

        # Verify preset structure
        assert "url" in MCP_PRESETS["marimo"]
        assert "url" in MCP_PRESETS["context7"]

    def test_append_presets_no_presets_list(self):
        """Test append_presets with config that has no presets list."""
        config = MCPConfig(
            mcpServers={
                "custom": MCPServerStdioConfig(command="test", args=[])
            }
        )

        result = append_presets(config)

        # Should return config unchanged
        assert "custom" in result["mcpServers"]
        assert len(result["mcpServers"]) == 1

    def test_append_presets_empty_presets_list(self):
        """Test append_presets with empty presets list."""
        config = MCPConfig(mcpServers={}, presets=[])

        result = append_presets(config)

        assert len(result["mcpServers"]) == 0

    def test_append_presets_adds_marimo_preset(self):
        """Test that marimo preset is added when specified."""
        config = MCPConfig(mcpServers={}, presets=["marimo"])

        result = append_presets(config)

        assert "marimo" in result["mcpServers"]
        assert (
            result["mcpServers"]["marimo"]["url"]
            == MCP_PRESETS["marimo"]["url"]
        )

    def test_append_presets_adds_context7_preset(self):
        """Test that context7 preset is added when specified."""
        config = MCPConfig(mcpServers={}, presets=["context7"])

        result = append_presets(config)

        assert "context7" in result["mcpServers"]
        assert (
            result["mcpServers"]["context7"]["url"]
            == MCP_PRESETS["context7"]["url"]
        )

    def test_append_presets_adds_multiple_presets(self):
        """Test that multiple presets can be added."""
        config = MCPConfig(mcpServers={}, presets=["marimo", "context7"])

        result = append_presets(config)

        assert "marimo" in result["mcpServers"]
        assert "context7" in result["mcpServers"]
        assert len(result["mcpServers"]) == 2

    def test_append_presets_preserves_existing_servers(self):
        """Test that existing servers are preserved when adding presets."""
        config = MCPConfig(
            mcpServers={
                "custom": MCPServerStdioConfig(command="test", args=[])
            },
            presets=["marimo"],
        )

        result = append_presets(config)

        assert "custom" in result["mcpServers"]
        assert "marimo" in result["mcpServers"]
        assert len(result["mcpServers"]) == 2

    def test_append_presets_does_not_override_existing(self):
        """Test that presets don't override existing servers with same name."""
        custom_url = "https://custom.marimo.app/mcp"
        config = MCPConfig(
            mcpServers={
                "marimo": MCPServerStreamableHttpConfig(url=custom_url)
            },
            presets=["marimo"],
        )

        result = append_presets(config)

        # Original server should be preserved
        assert result["mcpServers"]["marimo"]["url"] == custom_url
        assert len(result["mcpServers"]) == 1

    def test_append_presets_does_not_mutate_original(self):
        """Test that append_presets doesn't mutate the original config."""
        config = MCPConfig(mcpServers={}, presets=["marimo"])

        result = append_presets(config)

        # Original config should be unchanged
        assert "marimo" not in config["mcpServers"]
        # Result should have the preset
        assert "marimo" in result["mcpServers"]


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
    def test_stdio_connector_create(self, mock_stdio_client):
        """Test STDIO transport creation."""
        mock_context = AsyncMock()
        mock_stdio_client.return_value = mock_context

        # Create connector and test connection
        connector = StdioTransportConnector()
        config = MCPServerStdioConfig(
            command="python", args=["server.py"], env={"TEST_VAR": "value"}
        )
        server_def = MCPServerDefinition(
            name="test", transport=MCPTransportType.STDIO, config=config
        )

        transport = connector.create(server_def)

        assert transport is mock_context
        parameters = mock_stdio_client.call_args.args[0]
        assert parameters.command == "python"
        assert parameters.args == ["server.py"]
        assert parameters.env is not None
        assert parameters.env["TEST_VAR"] == "value"

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    @patch("httpx2.AsyncClient")
    @patch("mcp.client.streamable_http.streamable_http_client")
    async def test_http_connector_create(
        self, mock_streamable_http_client, mock_httpx_client
    ):
        """Test HTTP transport creation."""
        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(
            return_value=(mock_read, mock_write)
        )
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_streamable_http_client.return_value = mock_context

        mock_httpx_context = AsyncMock()
        mock_httpx_client.return_value = mock_httpx_context
        mock_httpx_context.__aenter__ = AsyncMock(
            return_value=mock_httpx_context
        )
        mock_httpx_context.__aexit__ = AsyncMock(return_value=None)

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

        transport = connector.create(server_def)
        async with transport as (read, write):
            assert read == mock_read
            assert write == mock_write

        mock_httpx_client.assert_called_once()
        http_client_kwargs = mock_httpx_client.call_args.kwargs
        assert http_client_kwargs["headers"] == {
            "Authorization": "Bearer token"
        }
        assert http_client_kwargs["follow_redirects"] is True
        timeout = http_client_kwargs["timeout"]
        assert timeout.connect == 30.0
        assert timeout.read == 300.0
        assert timeout.write == 30.0
        assert timeout.pool == 30.0
        mock_streamable_http_client.assert_called_once_with(
            "https://api.example.com/mcp",
            http_client=mock_httpx_context,
        )


class TestMCPClientConfiguration:
    """Test cases for MCPClient configuration parsing and initialization."""

    def test_init_with_empty_config(self):
        """Test MCPClient initialization with empty config."""
        client = MCPClient()
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
        client = MCPClient()

        # Parse the config to populate servers
        parsed_servers = client._parse_config(config)
        client.servers = parsed_servers

        assert len(client.servers) == len(expected_servers)
        for server_name in expected_servers:
            assert server_name in client.servers
            server_def = client.servers[server_name]
            assert server_def.name == server_name


@pytest.mark.skipif(
    not DependencyManager.mcp.has(), reason="MCP SDK not available"
)
class TestMCPClientReconfiguration:
    """Test cases for MCPClient dynamic reconfiguration functionality."""

    async def test_configure_noop_when_no_changes(self, mock_session_setup):
        """Test that configure() does nothing when config hasn't changed."""
        del mock_session_setup
        config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test", args=[], env={}
                )
            }
        )
        client = MCPClient()

        # Initial configure
        await client.configure(config)

        # Track calls to connect_to_server
        original_connect = client.connect_to_server
        connect_calls = []

        async def track_connect(server_name: str):
            connect_calls.append(server_name)
            return await original_connect(server_name)

        client.connect_to_server = track_connect

        # Configure with same config
        await client.configure(config)

        # Should not have called connect_to_server
        assert len(connect_calls) == 0

    async def test_configure_adds_new_servers(self, mock_session_setup):
        """Test that configure() adds new servers."""
        del mock_session_setup
        initial_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                )
            }
        )
        client = MCPClient()
        await client.configure(initial_config)

        # New config with additional server
        new_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                ),
                "server2": MCPServerStdioConfig(
                    command="test2", args=[], env={}
                ),
            }
        )

        # Mock the connection methods
        mock_connect = AsyncMock(return_value=True)
        with patch.object(client, "connect_to_server", mock_connect):
            await client.configure(new_config)

        # Verify server2 was added
        assert "server1" in client.servers
        assert "server2" in client.servers
        assert mock_connect.called
        # Should only connect to server2 (the new one)
        assert mock_connect.call_count == 1
        mock_connect.assert_called_with("server2")

    async def test_configure_removes_old_servers(self, mock_session_setup):
        """Test that configure() removes servers not in new config."""
        del mock_session_setup
        initial_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                ),
                "server2": MCPServerStdioConfig(
                    command="test2", args=[], env={}
                ),
            }
        )
        client = MCPClient()
        await client.configure(initial_config)

        # Create mock connections
        client.connections["server1"] = create_test_server_connection(
            "server1", MCPServerStatus.CONNECTED
        )
        client.connections["server2"] = create_test_server_connection(
            "server2", MCPServerStatus.CONNECTED
        )

        # New config with only server1
        new_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                )
            }
        )

        # Mock disconnect_from_server
        mock_disconnect = AsyncMock(return_value=True)
        with patch.object(client, "disconnect_from_server", mock_disconnect):
            await client.configure(new_config)

        # Verify server2 was removed
        assert "server1" in client.servers
        assert "server2" not in client.servers
        assert "server2" not in client.connections

        # Should have called disconnect for server2
        mock_disconnect.assert_called_once_with("server2")

    async def test_configure_updates_modified_servers(
        self, mock_session_setup
    ):
        """Test that configure() reconnects to servers with changed config."""
        del mock_session_setup
        initial_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=["--old"], env={}
                )
            }
        )
        client = MCPClient()
        await client.configure(initial_config)

        # Create mock connection
        client.connections["server1"] = create_test_server_connection(
            "server1", MCPServerStatus.CONNECTED
        )

        # New config with modified server1
        new_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=["--new"], env={}
                )
            }
        )

        # Mock methods
        mock_disconnect = AsyncMock(return_value=True)
        mock_connect = AsyncMock(return_value=True)
        with (
            patch.object(client, "disconnect_from_server", mock_disconnect),
            patch.object(client, "connect_to_server", mock_connect),
        ):
            await client.configure(new_config)

        # Should have disconnected and reconnected to server1
        mock_disconnect.assert_called_once_with("server1")
        mock_connect.assert_called_once_with("server1")

        # Verify config was updated
        assert client.servers["server1"].config["args"] == ["--new"]

    async def test_configure_mixed_changes(self, mock_session_setup):
        """Test configure() with add, remove, and update operations."""
        del mock_session_setup
        initial_config = MCPConfig(
            mcpServers={
                "keep_unchanged": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                ),
                "to_update": MCPServerStdioConfig(
                    command="test2", args=["--old"], env={}
                ),
                "to_remove": MCPServerStdioConfig(
                    command="test3", args=[], env={}
                ),
            }
        )
        client = MCPClient()
        await client.configure(initial_config)

        # Create mock connections
        for name in ["keep_unchanged", "to_update", "to_remove"]:
            client.connections[name] = create_test_server_connection(
                name, MCPServerStatus.CONNECTED
            )

        # New config
        new_config = MCPConfig(
            mcpServers={
                "keep_unchanged": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                ),
                "to_update": MCPServerStdioConfig(
                    command="test2", args=["--new"], env={}
                ),
                "to_add": MCPServerStdioConfig(
                    command="test4", args=[], env={}
                ),
            }
        )

        # Mock methods
        mock_disconnect = AsyncMock(return_value=True)
        mock_connect = AsyncMock(return_value=True)
        with (
            patch.object(client, "disconnect_from_server", mock_disconnect),
            patch.object(client, "connect_to_server", mock_connect),
        ):
            await client.configure(new_config)

        # Verify results
        assert "keep_unchanged" in client.servers
        assert "to_update" in client.servers
        assert "to_add" in client.servers
        assert "to_remove" not in client.servers
        assert "to_remove" not in client.connections

        # Verify disconnect was called for removed and updated
        assert mock_disconnect.call_count == 2
        disconnect_calls = [
            call[0][0] for call in mock_disconnect.call_args_list
        ]
        assert "to_remove" in disconnect_calls
        assert "to_update" in disconnect_calls

        # Verify connect was called for added and updated
        assert mock_connect.call_count == 2
        connect_calls = [call[0][0] for call in mock_connect.call_args_list]
        assert "to_add" in connect_calls
        assert "to_update" in connect_calls

    async def test_configure_connection_failures_logged(
        self, mock_session_setup
    ):
        """Test that configure() handles connection failures gracefully."""
        del mock_session_setup
        initial_config = MCPConfig(mcpServers={})
        client = MCPClient()
        await client.configure(initial_config)

        new_config = MCPConfig(
            mcpServers={
                "server1": MCPServerStdioConfig(
                    command="test1", args=[], env={}
                )
            }
        )

        # Mock connect_to_server to fail
        mock_connect = AsyncMock(side_effect=Exception("Connection failed"))
        with patch.object(client, "connect_to_server", mock_connect):
            # Should not raise, just log
            await client.configure(new_config)

        # Server should still be in registry even if connection failed
        assert "server1" in client.servers


class TestMCPClientToolManagement:
    """Test cases for MCPClient tool management functionality."""

    def test_create_namespaced_tool_name_no_conflict(self):
        """Test creating namespaced tool name without conflicts."""
        client = MCPClient()
        name = client._create_namespaced_tool_name("github", "create_issue")
        assert name == "mcp_github_create_issue"

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    def test_create_namespaced_tool_name_with_conflicts(self):
        """Test creating namespaced tool name with conflicts and counter resolution."""
        client = MCPClient()

        from mcp.types import Tool

        # Create first tool - should get base name
        name1 = client._create_namespaced_tool_name("github", "create_issue")
        assert name1 == "mcp_github_create_issue"

        # Add it to registry
        tool1 = Tool(
            name="create_issue",
            description="Test tool",
            input_schema={"type": "object"},
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
        client = MCPClient()
        from mcp.types import Tool

        # Create server connection
        connection = create_test_server_connection()

        # Create raw tools to add
        raw_tools = [
            Tool(
                name="tool1",
                description="Test tool 1",
                input_schema={"type": "object"},
            ),
            Tool(
                name="tool2",
                description="Test tool 2",
                input_schema={"type": "object"},
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
        client = MCPClient()
        from mcp.types import Tool

        # Create tools from different servers
        server1_tools = [
            (
                "mcp_server1_tool1",
                Tool(
                    name="tool1",
                    description="Test",
                    input_schema={"type": "object"},
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
                    input_schema={"type": "object"},
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
                    input_schema={"type": "object"},
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
        client = MCPClient()
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
                input_schema={"type": "object"},
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
        client = MCPClient()

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
                {"status": MCPServerStatus.CONNECTED, "client": AsyncMock()},
                "Tool 'nonexistent_tool' not found",
                id="tool_not_found",
            ),
            pytest.param(
                {"server_name": "test_server"},
                {"status": MCPServerStatus.DISCONNECTED, "client": None},
                "Server 'test_server' is not connected",
                id="server_not_connected",
            ),
            pytest.param(
                {"server_name": "test_server"},
                {"status": MCPServerStatus.CONNECTED, "client": None},
                "No active client for server 'test_server'",
                id="no_active_client",
            ),
        ],
    )
    async def test_invoke_tool_error_cases(
        self, tool_setup, connection_setup, expected_error_pattern
    ):
        """Test invoke_tool error handling scenarios."""
        client = MCPClient()
        from mcp.types import Tool

        # Setup tool if provided
        if tool_setup:
            mock_tool = Tool(
                name="test_tool",
                description="Test tool",
                input_schema={"type": "object"},
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
            connection.client = connection_setup["client"]
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
        client = MCPClient()
        from mcp.types import CallToolResult, TextContent

        # Setup tool
        mock_tool = create_test_tool()
        client.tool_registry["mcp_test_server_test_tool"] = mock_tool

        # Setup connection with mock client
        connection = create_test_server_connection(
            status=MCPServerStatus.CONNECTED, client=AsyncMock()
        )

        # Mock successful tool result
        expected_result = CallToolResult(
            content=[
                TextContent(type="text", text="Tool executed successfully")
            ]
        )
        connection.client.call_tool = AsyncMock(return_value=expected_result)
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

        # Verify client was called correctly
        connection.client.call_tool.assert_called_once_with(
            "test_tool", {"arg1": "value1"}
        )

    async def test_invoke_tool_timeout(self):
        """Test tool invocation timeout handling."""
        client = MCPClient()

        # Setup tool
        mock_tool = create_test_tool()
        client.tool_registry["mcp_test_server_test_tool"] = mock_tool

        # Setup connection with timeout
        connection = create_test_server_connection(
            timeout=0.1,  # Very short timeout
            status=MCPServerStatus.CONNECTED,
            client=AsyncMock(),
        )

        # Mock client to hang longer than timeout
        async def slow_call_tool(_name, _args):
            await asyncio.sleep(1)  # Longer than timeout

        connection.client.call_tool = AsyncMock(side_effect=slow_call_tool)
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

        client = MCPClient()

        # Create result
        content = [TextContent(**item) for item in result_content]
        result = CallToolResult(is_error=expected_is_error, content=content)

        # Test error detection
        assert client.is_error_result(result) == expected_is_error

        # Test text extraction
        text_contents = client.extract_text_content(result)
        assert len(text_contents) == expected_text_count

        for i, expected_text in enumerate(
            [item["text"] for item in result_content]
        ):
            assert text_contents[i] == expected_text

    def test_convert_structured_tool_result(self):
        from mcp.types import CallToolResult, TextContent

        client = MCPClient()
        result = CallToolResult(
            content=[TextContent(type="text", text="fallback")],
            structured_content={"rows": [{"value": 1}]},
        )

        assert client.convert_tool_result(result) == {"rows": [{"value": 1}]}

    def test_convert_non_text_tool_result(self):
        from mcp.types import CallToolResult, ImageContent

        client = MCPClient()
        result = CallToolResult(
            content=[
                ImageContent(
                    type="image", data="aW1hZ2U=", mime_type="image/png"
                )
            ]
        )

        assert client.convert_tool_result(result) == {
            "content": [
                {
                    "type": "image",
                    "data": "aW1hZ2U=",
                    "mimeType": "image/png",
                }
            ]
        }

    def test_format_structured_tool_error(self):
        from mcp.types import CallToolResult

        client = MCPClient()
        result = CallToolResult(
            is_error=True,
            content=[],
            structured_content={"reason": "denied", "code": 403},
        )

        assert client.format_tool_error(result) == (
            '{"code": 403, "reason": "denied"}'
        )


@pytest.mark.skipif(
    not DependencyManager.mcp.has(), reason="MCP SDK not available"
)
class TestMCPClientConnectionManagement:
    """Test cases for MCPClient connection management functionality."""

    async def test_discover_tools_success(self):
        """Test successful tool discovery from an MCP server."""
        client = MCPClient()
        from mcp.types import ListToolsResult, Tool

        # Create mock connection with a client
        mock_client = AsyncMock()
        connection = create_test_server_connection(client=mock_client)

        # Mock tools response
        mock_tools = [
            Tool(
                name="tool1",
                description="First tool",
                input_schema={"type": "object"},
            ),
            Tool(
                name="tool2",
                description="Second tool",
                input_schema={"type": "object"},
            ),
        ]
        mock_response = ListToolsResult(tools=mock_tools)
        mock_client.list_tools = AsyncMock(return_value=mock_response)

        # Test tool discovery
        await client._discover_tools(connection)

        # Verify tools were added
        assert len(connection.tools) == 2
        assert "mcp_test_server_tool1" in client.tool_registry
        assert "mcp_test_server_tool2" in client.tool_registry

        # Verify client was called
        mock_client.list_tools.assert_called_once_with(cursor=None)

    async def test_discover_tools_follows_pagination(self):
        from mcp.types import ListToolsResult, Tool

        client = MCPClient()
        mock_client = AsyncMock()
        connection = create_test_server_connection(client=mock_client)
        mock_client.list_tools.side_effect = [
            ListToolsResult(
                tools=[
                    Tool(
                        name="tool1",
                        description="First tool",
                        input_schema={"type": "object"},
                    )
                ],
                next_cursor="page-2",
            ),
            ListToolsResult(
                tools=[
                    Tool(
                        name="tool2",
                        description="Second tool",
                        input_schema={"type": "object"},
                    )
                ]
            ),
        ]

        await client._discover_tools(connection)

        assert set(client.tool_registry) == {
            "mcp_test_server_tool1",
            "mcp_test_server_tool2",
        }
        assert mock_client.list_tools.await_args_list == [
            (((), {"cursor": None})),
            (((), {"cursor": "page-2"})),
        ]

    async def test_discover_tools_is_atomic_on_failure(self):
        client = MCPClient()
        existing_tool = create_test_tool(name="existing")
        connection = create_test_server_connection(client=AsyncMock())
        connection.tools = [existing_tool]
        client.connections["test_server"] = connection
        client.tool_registry["mcp_test_server_existing"] = existing_tool
        connection.client.list_tools.side_effect = RuntimeError("failed")

        with pytest.raises(RuntimeError, match="failed"):
            await client._discover_tools(connection)

        assert connection.tools == [existing_tool]
        assert set(client.tool_registry) == {"mcp_test_server_existing"}

    async def test_discover_tools_no_client(self):
        """Test tool discovery with no active client."""
        client = MCPClient()

        connection = create_test_server_connection(client=None)

        with pytest.raises(RuntimeError, match="No active client"):
            await client._discover_tools(connection)

        # Verify no tools were added
        assert len(connection.tools) == 0
        assert len(client.tool_registry) == 0

    @patch("mcp.Client")
    async def test_connect_to_server_success(
        self,
        mock_client_class,
    ):
        """Test successful server connection with complete flow."""
        mock_connection_client = AsyncMock()
        mock_connection_client.__aenter__ = AsyncMock(
            return_value=mock_connection_client
        )
        mock_connection_client.__aexit__ = AsyncMock(return_value=None)
        mock_connection_client.list_tools.return_value.tools = []
        mock_connection_client.list_tools.return_value.next_cursor = None
        mock_client_class.return_value = mock_connection_client
        transport = AsyncMock()

        with patch(
            "marimo._server.ai.mcp.StdioTransportConnector.create",
            return_value=transport,
        ):
            config = MCPConfig(
                mcpServers={
                    "test_server": MCPServerStdioConfig(
                        command="python", args=["test.py"], env={}
                    )
                }
            )
            client = MCPClient()
            await client.configure(config)

            # Test connection
            result = await client.connect_to_server("test_server")

            assert result is True
            assert "test_server" in client.connections
            assert (
                client.connections["test_server"].status
                == MCPServerStatus.CONNECTED
            )
            mock_client_class.assert_called_once_with(
                transport,
                mode="auto",
                read_timeout_seconds=30.0,
            )
            await client.disconnect_from_server("test_server")

    @patch("mcp.Client")
    async def test_connect_to_server_fails_when_discovery_fails(
        self, mock_client_class
    ):
        mock_connection_client = AsyncMock()
        mock_connection_client.__aenter__.return_value = mock_connection_client
        mock_connection_client.list_tools.side_effect = RuntimeError(
            "discovery failed"
        )
        mock_client_class.return_value = mock_connection_client
        client = MCPClient()
        client.servers["test_server"] = create_test_server_definition()

        with patch(
            "marimo._server.ai.mcp.StdioTransportConnector.create",
            return_value=AsyncMock(),
        ):
            result = await client.connect_to_server("test_server")

        assert result is False
        connection = client.connections["test_server"]
        assert connection.status == MCPServerStatus.ERROR
        assert connection.tools == []
        assert connection.error_message is not None
        assert "discovery failed" in connection.error_message

    @patch("mcp.Client")
    async def test_connect_to_server_cancels_timed_out_lifecycle(
        self, mock_client_class
    ):
        async def wait_forever():
            await asyncio.Event().wait()

        mock_connection_client = AsyncMock()
        mock_connection_client.__aenter__.side_effect = wait_forever
        mock_client_class.return_value = mock_connection_client
        client = MCPClient()
        client.servers["test_server"] = create_test_server_definition(
            timeout=0.01
        )

        with patch(
            "marimo._server.ai.mcp.StdioTransportConnector.create",
            return_value=AsyncMock(),
        ):
            result = await client.connect_to_server("test_server")

        assert result is False
        connection = client.connections["test_server"]
        assert connection.status == MCPServerStatus.ERROR
        assert connection.connection_task is not None
        assert connection.connection_task.cancelled()
        assert await client.disconnect_from_server("test_server") is True

    @patch("mcp.Client")
    async def test_cancelling_connection_closes_lifecycle(
        self, mock_client_class
    ):
        discovery_started = asyncio.Event()

        async def wait_forever(*, cursor):
            assert cursor is None
            discovery_started.set()
            await asyncio.Event().wait()

        mock_connection_client = AsyncMock()
        mock_connection_client.__aenter__.return_value = mock_connection_client
        mock_connection_client.list_tools.side_effect = wait_forever
        mock_client_class.return_value = mock_connection_client
        client = MCPClient()
        client.servers["test_server"] = create_test_server_definition()

        with patch(
            "marimo._server.ai.mcp.StdioTransportConnector.create",
            return_value=AsyncMock(),
        ):
            connect_task = asyncio.create_task(
                client.connect_to_server("test_server")
            )
            await asyncio.wait_for(discovery_started.wait(), timeout=1)
            connect_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await connect_task

        connection = client.connections["test_server"]
        assert connection.status == MCPServerStatus.DISCONNECTED
        assert connection.connection_task is not None
        assert connection.connection_task.cancelled()
        mock_connection_client.__aexit__.assert_awaited_once()

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
            config["mcpServers"]["test_server"] = MCPServerStdioConfig(
                command="python", args=["test.py"]
            )

        client = MCPClient()
        await client.configure(config)

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

    async def test_connect_to_all_servers_mixed_results(self):
        """Test connecting to multiple servers with mixed success/failure."""
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
        client = MCPClient()
        client.servers = client._parse_config(config)

        with patch.object(
            client,
            "connect_to_server",
            new=AsyncMock(side_effect=[True, False]),
        ):
            results = await client.connect_to_all_servers()

            assert len(results) == 2
            assert results["server1"] is True
            assert results["server2"] is False


@pytest.mark.skipif(
    not DependencyManager.mcp.has(), reason="MCP SDK not available"
)
class TestMCPClientDisconnectionManagement:
    """Test cases for MCPClient disconnection functionality."""

    async def test_disconnect_from_server_success(self):
        """Test successful disconnection from a connected server."""
        client = MCPClient()

        # Setup a connected server using existing patterns
        connection = create_test_server_connection(
            name="test_server",
            status=MCPServerStatus.CONNECTED,
            client=AsyncMock(),
        )

        connection_task = create_connection_task()
        disconnect_event = asyncio.Event()

        connection.connection_task = connection_task
        connection.disconnect_event = disconnect_event
        client.connections["test_server"] = connection

        # Call actual disconnect method
        result = await client.disconnect_from_server("test_server")

        # Verify successful disconnection
        assert result is True
        assert disconnect_event.is_set()  # Event was signaled

    async def test_disconnect_from_server_already_disconnected(self):
        """Test disconnection from server that's already disconnected."""
        client = MCPClient()

        # Call disconnect on non-existent server
        result = await client.disconnect_from_server("nonexistent_server")

        # Should return True (idempotent operation)
        assert result is True

    async def test_disconnect_from_server_with_exception(self):
        """Test disconnection failure handling (validates our new comment)."""
        client = MCPClient()

        # Setup connection with task that will raise exception when awaited
        connection = create_test_server_connection(
            name="test_server", status=MCPServerStatus.CONNECTED
        )

        # Create event to signal when task has started
        task_started = asyncio.Event()

        # Create a long-running task that will fail when awaited
        async def blocking_failing_task():
            task_started.set()  # Signal task has started
            await asyncio.sleep(0.1)  # Simulate work
            raise RuntimeError("Simulated disconnection failure")

        # Start the task
        failing_task = asyncio.create_task(blocking_failing_task())
        # Wait for task to actually start (deterministic)
        await asyncio.wait_for(task_started.wait(), timeout=1.0)

        connection.connection_task = failing_task
        connection.disconnect_event = asyncio.Event()
        client.connections["test_server"] = connection

        # Call disconnect - should handle exception gracefully
        result = await client.disconnect_from_server("test_server")

        # Should return False but not raise exception (non-blocking behavior)
        assert result is False

    async def test_disconnect_from_server_cleanup_verification(self):
        """Test that disconnection properly cleans up server state."""
        client = MCPClient()

        # Setup connected server with tools and monitoring
        connection = create_test_server_connection(
            name="test_server",
            status=MCPServerStatus.CONNECTED,
            client=AsyncMock(),
        )

        # Add tools to verify they get cleaned up
        mock_tools = [
            create_test_tool(name="tool1", server_name="test_server"),
            create_test_tool(name="tool2", server_name="test_server"),
        ]

        for i, tool in enumerate(mock_tools):
            if tool:
                namespaced_name = f"mcp_test_server_tool{i + 1}"
                client.tool_registry[namespaced_name] = tool
                connection.tools.append(tool)

        # Add health monitoring task
        health_task = AsyncMock()
        client.health_check_tasks["test_server"] = health_task

        connection_task = create_connection_task()
        connection.connection_task = connection_task
        connection.disconnect_event = asyncio.Event()
        client.connections["test_server"] = connection

        # Disconnect
        result = await client.disconnect_from_server("test_server")

        # Verify cleanup happens in _connection_lifecycle finally block
        assert result is True
        # Note: Tool cleanup happens in _connection_lifecycle finally block,
        # not directly in disconnect_from_server

    @pytest.mark.parametrize(
        "server_setups",
        [
            pytest.param(
                [
                    {"name": "server1", "should_succeed": True},
                    {"name": "server2", "should_succeed": True},
                ],
                id="all_succeed",
            ),
            pytest.param(
                [
                    {"name": "server1", "should_succeed": True},
                    {"name": "server2", "should_succeed": False},
                ],
                id="mixed_results",
            ),
            pytest.param(
                [
                    {"name": "server1", "should_succeed": False},
                    {"name": "server2", "should_succeed": False},
                ],
                id="all_fail",
            ),
        ],
    )
    async def test_disconnect_from_all_servers_scenarios(self, server_setups):
        """Test disconnect_from_all_servers with various success/failure combinations."""
        client = MCPClient()

        # Setup connections based on test parameters
        for setup in server_setups:
            connection = create_test_server_connection(
                name=setup["name"], status=MCPServerStatus.CONNECTED
            )

            error = (
                None
                if setup["should_succeed"]
                else Exception("Simulated failure")
            )
            connection_task = create_connection_task(error)

            connection.connection_task = connection_task
            connection.disconnect_event = asyncio.Event()
            client.connections[setup["name"]] = connection

        # Call actual disconnect_from_all_servers method
        await client.disconnect_from_all_servers()

        # Verify disconnect events were set (disconnect_from_all_servers doesn't return results)
        for setup in server_setups:
            connection = client.connections[setup["name"]]
            # Event should be set regardless of success/failure (signal was sent)
            assert connection.disconnect_event.is_set()

    async def test_disconnect_from_all_servers_with_health_monitoring(self):
        """Test that disconnect_from_all_servers cancels health monitoring first."""
        client = MCPClient()

        # Setup connections with health monitoring tasks
        server_names = ["server1", "server2"]
        for name in server_names:
            # Create connection
            connection = create_test_server_connection(
                name=name, status=MCPServerStatus.CONNECTED
            )
            connection_task = create_connection_task()
            connection.connection_task = connection_task
            connection.disconnect_event = asyncio.Event()
            client.connections[name] = connection

            # Create health monitoring task
            health_task = AsyncMock()
            health_task.cancel = AsyncMock()
            client.health_check_tasks[name] = health_task

        # Mock _cancel_health_monitoring to verify it's called
        with patch.object(
            client, "_cancel_health_monitoring", new_callable=AsyncMock
        ) as mock_cancel:
            await client.disconnect_from_all_servers()

            # Verify health monitoring was cancelled first
            mock_cancel.assert_called_once_with()

    async def test_disconnect_cross_task_scenario(self):
        """Test disconnection in cross-task scenarios (like server shutdown)."""
        client = MCPClient()

        # Setup connection that simulates cross-task issues
        connection = create_test_server_connection(
            name="test_server", status=MCPServerStatus.CONNECTED
        )

        # Create event to signal when task has started
        task_started = asyncio.Event()

        # Create a task that simulates cross-task lifecycle issues
        async def cross_task_error():
            task_started.set()  # Signal task has started
            await asyncio.sleep(0.1)  # Simulate work
            raise RuntimeError("Task was destroyed but it is pending!")

        # Start the task
        cross_task = asyncio.create_task(cross_task_error())
        # Wait for task to actually start (deterministic)
        await asyncio.wait_for(task_started.wait(), timeout=1.0)

        connection.connection_task = cross_task
        connection.disconnect_event = asyncio.Event()
        client.connections["test_server"] = connection

        # This should handle the cross-task error gracefully (non-blocking)
        result = await client.disconnect_from_server("test_server")

        # Should return False (failure) but not raise exception
        assert result is False

        # Event should still be signaled to attempt cleanup
        assert connection.disconnect_event.is_set()


class TestMCPClientHealthMonitoring:
    """Test cases for MCPClient health monitoring functionality."""

    @pytest.mark.skipif(
        not DependencyManager.mcp.has(), reason="MCP SDK not available"
    )
    async def test_perform_health_check_success(self):
        """Test successful health check."""
        client = MCPClient()

        # Create connection with mock client
        server_def = MCPServerDefinitionFactory.from_config(
            "test", MCPServerStdioConfig(command="test", args=[])
        )
        connection = MCPServerConnection(definition=server_def)
        connection.client = AsyncMock()
        connection.client.list_tools = AsyncMock()
        client.connections["test"] = connection

        result = await client._perform_health_check("test")

        assert result is True
        connection.client.list_tools.assert_called_once_with(
            cache_mode="refresh"
        )
        # Note: last_health_check is updated by the caller (_monitor_server_health), not _perform_health_check
        assert connection.last_health_check == 0  # Should remain unchanged

    @pytest.mark.parametrize(
        ("client_setup", "discovery_behavior", "expected_result"),
        [
            pytest.param(
                None,  # No client
                None,
                False,
                id="no_client",
            ),
            pytest.param(
                AsyncMock(),  # Valid session
                Exception("Discovery failed"),
                False,
                id="discovery_exception",
            ),
        ],
    )
    async def test_perform_health_check_failure_cases(
        self, client_setup, discovery_behavior, expected_result
    ):
        """Test health check failure scenarios."""
        client = MCPClient()

        # Create connection
        server_def = MCPServerDefinitionFactory.from_config(
            "test", MCPServerStdioConfig(command="test", args=[])
        )
        connection = MCPServerConnection(definition=server_def)
        connection.client = client_setup

        if client_setup and discovery_behavior:
            connection.client.list_tools = AsyncMock(
                side_effect=discovery_behavior
            )

        client.connections["test"] = connection

        result = await client._perform_health_check("test")

        assert result == expected_result
        # Note: _perform_health_check doesn't update connection status directly
        # Status updates happen in the calling code (_monitor_server_health)

    async def test_perform_health_check_timeout(self):
        """Test health check timeout handling."""
        client = MCPClient()
        client.health_check_timeout = 0.1  # Very short timeout

        # Create connection with a client that hangs
        server_def = MCPServerDefinitionFactory.from_config(
            "test", MCPServerStdioConfig(command="test", args=[])
        )
        connection = MCPServerConnection(definition=server_def)
        connection.client = AsyncMock()

        # Create a coroutine that sleeps longer than timeout
        async def slow_discovery(*, cache_mode):
            assert cache_mode == "refresh"
            await asyncio.sleep(1)

        connection.client.list_tools = AsyncMock(side_effect=slow_discovery)
        client.connections["test"] = connection

        result = await client._perform_health_check("test")

        assert result is False
        # Note: _perform_health_check doesn't update connection status directly
        # Status updates happen in the calling code (_monitor_server_health)

    async def test_health_monitor_closes_after_failure_threshold(self):
        client = MCPClient()
        client.health_check_interval = 0
        client.health_check_failure_threshold = 3
        connection = create_test_server_connection(
            name="test", status=MCPServerStatus.CONNECTED, client=AsyncMock()
        )
        connection.disconnect_event = asyncio.Event()
        client.connections["test"] = connection
        client._perform_health_check = AsyncMock(return_value=False)

        task = asyncio.create_task(client._monitor_server_health("test"))
        client.health_check_tasks["test"] = task
        await asyncio.wait_for(task, timeout=1)

        assert client._perform_health_check.await_count == 3
        assert connection.status == MCPServerStatus.ERROR
        assert connection.disconnect_event.is_set()
        assert "test" not in client.health_check_tasks

    async def test_cancel_health_monitoring_removes_task_once(self):
        client = MCPClient()
        client.health_check_interval = 60
        task = asyncio.create_task(client._monitor_server_health("test"))
        client.health_check_tasks["test"] = task

        await client._cancel_health_monitoring("test")

        assert task.done()
        assert "test" not in client.health_check_tasks


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
        assert connection.definition.config["command"] == "python"
        assert connection.definition.config.get("args") == ["test.py"]
        assert connection.definition.config.get("env") == {"TEST": "value"}
        assert connection.status == MCPServerStatus.DISCONNECTED
        assert connection.client is None
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
    async def test_get_mcp_client_with_custom_config(self):
        """Test get_mcp_client with custom configuration."""
        # Reset global client for this test
        import marimo._server.ai.mcp.client as client_module

        client_module._mcp_client = None

        custom_config = MCPConfig(
            mcpServers={
                "custom_server": MCPServerStdioConfig(
                    command="custom", args=["--test"], env={}
                )
            }
        )

        client = get_mcp_client()
        await client.configure(custom_config)
        assert "custom_server" in client.servers
