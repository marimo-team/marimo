# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._server.ai.mcp.transport import MCPTransportType

if TYPE_CHECKING:
    from marimo._config.config import (
        MCPConfig,
        MCPServerConfig,
    )

LOGGER = _loggers.marimo_logger()


# MCP Server Presets
MCP_PRESETS: dict[str, MCPServerConfig] = {
    "marimo": {
        "url": "https://mcp.marimo.app/mcp",
    },
    "context7": {
        "url": "https://mcp.context7.com/mcp",
    },
}


def append_presets(config: MCPConfig) -> MCPConfig:
    """Append preset MCP servers to the configuration.

    Presets are added to the mcpServers dict if they are specified in the
    'presets' list and not already present in mcpServers.

    Args:
        config: MCP configuration potentially containing a presets list

    Returns:
        Updated configuration with presets appended to mcpServers
    """
    from marimo._config.config import MCPConfig

    presets_to_add = config.get("presets", [])
    if not presets_to_add:
        return config

    # Create a copy to avoid mutating the original
    updated_config = MCPConfig(mcpServers=config["mcpServers"].copy())

    # Add preset servers if not already present
    for preset_name in presets_to_add:
        if preset_name not in updated_config["mcpServers"]:
            if preset_name in MCP_PRESETS:
                updated_config["mcpServers"][preset_name] = MCP_PRESETS[
                    preset_name
                ]

    return updated_config


def is_mcp_config_empty(config: MCPConfig | None) -> bool:
    """Check if the MCP configuration is empty."""
    if config is None:
        return True
    return not config.get("mcpServers") and not config.get("presets")


@dataclass
class MCPServerDefinition:
    """Runtime server definition wrapping config with computed fields."""

    name: str
    transport: MCPTransportType
    config: MCPServerConfig
    timeout: float = 30.0

    def __eq__(self, other: object) -> bool:
        """Check if two server definitions are equal based on config content."""
        if not isinstance(other, MCPServerDefinition):
            return NotImplemented
        return (
            self.name == other.name
            and self.transport == other.transport
            and self.config == other.config
            and self.timeout == other.timeout
        )

    def __hash__(self) -> int:
        """Hash based on name for use in sets/dicts."""
        return hash(self.name)


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


@dataclass
class MCPConfigDiff:
    """Represents changes between two MCP configurations."""

    servers_to_add: dict[str, MCPServerDefinition]
    servers_to_remove: set[str]
    servers_to_update: dict[str, MCPServerDefinition]
    servers_unchanged: set[str]

    def has_changes(self) -> bool:
        """Check if there are any changes in the configuration."""
        return bool(
            self.servers_to_add
            or self.servers_to_remove
            or self.servers_to_update
        )


class MCPConfigComparator:
    """Utility for comparing MCP configurations and computing differences."""

    @staticmethod
    def compute_diff(
        current_servers: dict[str, MCPServerDefinition],
        new_servers: dict[str, MCPServerDefinition],
    ) -> MCPConfigDiff:
        """Compare current and new server configurations.

        Args:
            current_servers: Currently configured servers
            new_servers: New server configuration

        Returns:
            MCPConfigDiff describing the changes needed
        """
        current_names = set(current_servers.keys())
        new_names = set(new_servers.keys())

        # Servers that need to be removed
        servers_to_remove = current_names - new_names

        # Servers that need to be added
        servers_to_add = {
            name: new_servers[name] for name in (new_names - current_names)
        }

        # Servers that might need to be updated
        common_servers = current_names & new_names
        servers_to_update: dict[str, MCPServerDefinition] = {}
        servers_unchanged: set[str] = set()

        for name in common_servers:
            current_def = current_servers[name]
            new_def = new_servers[name]

            # Check if server definition has changed
            if current_def != new_def:
                servers_to_update[name] = new_def
            else:
                servers_unchanged.add(name)

        return MCPConfigDiff(
            servers_to_add=servers_to_add,
            servers_to_remove=servers_to_remove,
            servers_to_update=servers_to_update,
            servers_unchanged=servers_unchanged,
        )
