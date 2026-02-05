# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import socket
from typing import TYPE_CHECKING, Any, Optional

from marimo import _loggers
from marimo._server.ai.mcp.config import is_mcp_config_empty
from marimo._server.ai.tools.tool_manager import setup_tool_manager
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.api.interrupt import InterruptHandler
from marimo._server.api.utils import open_url_in_browser
from marimo._server.file_router import AppFileRouter
from marimo._server.lsp import any_lsp_server_running
from marimo._server.print import (
    print_experimental_features,
    print_mcp_client,
    print_mcp_server,
    print_shutdown,
    print_startup,
)
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import AuthToken
from marimo._server.utils import initialize_mimetypes
from marimo._server.uvicorn_utils import close_uvicorn
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette

LOGGER = _loggers.marimo_logger()

background_tasks: set[asyncio.Task[Any]] = set()


@contextlib.asynccontextmanager
async def lsp(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    user_config = state.config_manager.get_config()
    session_mgr = state.session_manager

    # Only start the LSP server in Edit mode
    if session_mgr.mode != SessionMode.EDIT:
        yield
        return

    # Only start the LSP server if any LSP servers are configured
    if not any_lsp_server_running(user_config):
        yield
        return

    LOGGER.debug("Language Servers are enabled")
    # Start LSP server in background to avoid blocking server startup
    task = asyncio.create_task(session_mgr.start_lsp_server())
    background_tasks.add(task)  # Keep a reference to prevent GC
    task.add_done_callback(background_tasks.discard)  # Clean up when done

    yield

    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@contextlib.asynccontextmanager
async def tool_manager(app: Starlette) -> AsyncIterator[None]:
    try:
        # Initialize and attach to app state
        setup_tool_manager(app)

    except Exception as e:  # pragma: no cover - defensive
        LOGGER.warning("Failed to initialize ToolManager: %s", e)

    yield


@contextlib.asynccontextmanager
async def mcp(app: Starlette) -> AsyncIterator[None]:
    if TYPE_CHECKING:
        from marimo._server.ai.mcp import MCPClient

    state = AppState.from_app(app)
    session_mgr = state.session_manager
    user_config = state.config_manager.get_config()
    mcp_config = user_config.get("mcp")

    # Only start MCP servers in Edit mode
    if session_mgr.mode != SessionMode.EDIT:
        yield
        return

    # Only start MCP servers if the config is not empty
    if not mcp_config or is_mcp_config_empty(mcp_config):
        yield
        return

    async def background_connect_mcp_servers() -> Optional[MCPClient]:
        try:
            from marimo._server.ai.mcp import get_mcp_client

            mcp_client = get_mcp_client()
            print_mcp_client(mcp_config)
            await mcp_client.configure(mcp_config)

            LOGGER.info(
                f"MCP servers connected: {list(mcp_client.servers.keys())}"
            )
            return mcp_client
        except Exception as e:
            LOGGER.warning(f"Failed to connect MCP servers: {e}")
            return None

    task = asyncio.create_task(background_connect_mcp_servers())
    background_tasks.add(task)  # Keep a reference to prevent GC
    task.add_done_callback(background_tasks.discard)  # Clean up when done

    yield

    # Shutdown
    task.cancel()
    try:
        mcp_client = await task
        if mcp_client:
            LOGGER.info("Disconnecting from all MCP servers")
            await mcp_client.disconnect_from_all_servers()
            LOGGER.info("Successfully disconnected from all MCP servers")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        LOGGER.error(f"Error during MCP cleanup: {e}")


@contextlib.asynccontextmanager
async def open_browser(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    if not state.headless:
        url = _startup_url(state)
        user_config = state.config_manager.get_config()
        browser = user_config["server"]["browser"]
        # Wait 20ms for the server to start and then open the browser, but this
        # function must complete
        asyncio.get_running_loop().call_later(
            0.02, open_url_in_browser, browser, url
        )
    yield


@contextlib.asynccontextmanager
async def logging(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    manager: SessionManager = state.session_manager
    quiet = state.quiet
    file_router = manager.file_router
    mcp_server_enabled = state.mcp_server_enabled
    skew_protection_enabled = state.skew_protection

    # Startup message
    if not quiet:
        file = file_router.maybe_get_single_file()
        print_startup(
            file_name=file.name if file else None,
            url=_startup_url(state),
            run=manager.mode == SessionMode.RUN,
            new=file_router.get_unique_file_key() == AppFileRouter.NEW_FILE,
            network=state.host == "0.0.0.0",
        )

        print_experimental_features(state.config_manager.get_config())

        if mcp_server_enabled:
            mcp_url = _mcp_startup_url(state)
            server_token = None
            if skew_protection_enabled:
                server_token = str(state.session_manager.skew_protection_token)
            print_mcp_server(mcp_url, server_token)

    yield

    # Shutdown message
    if not quiet:
        print_shutdown()


@contextlib.asynccontextmanager
async def signal_handler(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    manager = state.session_manager

    # Interrupt handler
    def shutdown() -> None:
        manager.shutdown()
        if state.server:
            close_uvicorn(state.server)

    InterruptHandler(
        quiet=state.quiet,
        shutdown=shutdown,
    ).register()
    yield


@contextlib.asynccontextmanager
async def etc(app: Starlette) -> AsyncIterator[None]:
    del app
    # Mimetypes
    initialize_mimetypes()
    yield


def _startup_url(state: AppStateBase) -> str:
    host = state.host
    port = state.port
    try:
        # pretty printing:
        # if the address maps to localhost, print "localhost" to stdout
        if (
            socket.getnameinfo((host, port), socket.NI_NOFQDN)[0]
            == "localhost"
        ):
            host = "localhost"
    except Exception:
        # aggressive try/except in case of platform-specific quirks;
        # nothing to handle, since the `try` logic is just for pretty
        # printing the host name
        ...

    url = f"http://{host}:{port}{state.base_url}"
    if port == 80:
        url = f"http://{host}{state.base_url}"
    elif port == 443:
        url = f"https://{host}{state.base_url}"

    if AuthToken.is_empty(state.session_manager.auth_token):
        return url
    return f"{url}?access_token={str(state.session_manager.auth_token)}"


def _mcp_startup_url(state: AppStateBase) -> str:
    host = state.host
    port = state.port
    base_url = state.base_url

    # Handle localhost pretty printing (same logic as _startup_url)
    try:
        if (
            socket.getnameinfo((host, port), socket.NI_NOFQDN)[0]
            == "localhost"
        ):
            host = "localhost"
    except Exception:
        ...

    # Construct MCP endpoint URL
    mcp_prefix = "/mcp"
    mcp_name = "server"
    full_mcp_path = f"{mcp_prefix}/{mcp_name}"
    url = f"http://{host}:{port}{base_url}{full_mcp_path}"
    if port == 80:
        url = f"http://{host}{base_url}{full_mcp_path}"
    elif port == 443:
        url = f"https://{host}{base_url}{full_mcp_path}"

    # Add access token if not empty
    if AuthToken.is_empty(state.session_manager.auth_token):
        return url
    return f"{url}?access_token={str(state.session_manager.auth_token)}"
