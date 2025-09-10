# Copyright 2025 Marimo. All rights reserved.
import contextlib
from collections.abc import AsyncIterator

from starlette.applications import Starlette

from marimo._loggers import marimo_logger

LOGGER = marimo_logger()


@contextlib.asynccontextmanager
async def mcp_server_lifespan(app: Starlette) -> AsyncIterator[None]:
    """Lifespan for MCP server functionality (exposing marimo as MCP server)."""

    try:
        # Import here to avoid circular imports and optional dependency issues
        from marimo._mcp.server.main import setup_mcp_server

        session_manager = setup_mcp_server(app)

        async with session_manager.run():
            LOGGER.info("MCP server session manager started")
            # Session manager owns request lifecycle during app run
            yield

    except ImportError as e:
        LOGGER.warning(f"MCP server dependencies not available: {e}")
        yield
        return
    except Exception as e:
        LOGGER.error(f"Failed to start MCP server: {e}")
        raise
