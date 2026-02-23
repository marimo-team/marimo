# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from marimo._types.lifespan import Lifespan

McpType = Literal["tools", "code-mode"]

if TYPE_CHECKING:
    from starlette.applications import Starlette


def setup_mcp_server(
    app: Starlette, mode: McpType, *, allow_remote: bool = False
) -> Lifespan[Starlette]:
    """Set up the MCP server for the given mode.

    Returns the corresponding lifespan context manager that must be
    included in the application's lifespan chain.
    """
    if mode == "tools":
        from marimo._mcp.server.lifespan import mcp_server_lifespan
        from marimo._mcp.server.main import setup_mcp_server as _setup_tools

        _setup_tools(app, allow_remote=allow_remote)
        return mcp_server_lifespan
    elif mode == "code-mode":
        from marimo._mcp.code_server.lifespan import code_mcp_server_lifespan
        from marimo._mcp.code_server.main import (
            setup_code_mcp_server as _setup_code,
        )

        _setup_code(app, allow_remote=allow_remote)
        return code_mcp_server_lifespan
    raise ValueError(f"Unknown MCP mode: {mode}")
