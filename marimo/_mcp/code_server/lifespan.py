# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from marimo._loggers import marimo_logger

LOGGER = marimo_logger()

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette


@contextlib.asynccontextmanager
async def code_mcp_server_lifespan(app: Starlette) -> AsyncIterator[None]:
    """Lifespan for Code Mode MCP server functionality."""

    try:
        code_mcp_app = getattr(app.state, "code_mcp", None)
        if code_mcp_app is None:
            LOGGER.warning("Code MCP server not found in app state")
            yield
            return

        async with code_mcp_app.session_manager.run():
            LOGGER.info("Code MCP server session manager started")
            yield

    except ImportError as e:
        LOGGER.warning(f"Code MCP server dependencies not available: {e}")
        yield
        return
    except Exception as e:
        LOGGER.error(f"Failed to start Code MCP server: {e}")
        yield
        return
