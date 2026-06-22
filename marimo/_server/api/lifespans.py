# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._server.ai.mcp.config import is_mcp_config_empty
from marimo._server.ai.tools.tool_manager import setup_tool_manager
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.api.interrupt import InterruptHandler
from marimo._server.api.utils import (
    format_url_host,
    open_url_in_browser,
)
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
from marimo._server.workspace import NEW_FILE
from marimo._session.model import SessionMode
from marimo._utils.asyncio_utils import cancel_and_wait, supervised_task
from marimo._utils.subprocess import cancel_pending_reaps

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
    task = supervised_task(
        session_mgr.start_lsp_server(),
        name="lsp.start",
        registry=background_tasks,
    )

    yield

    await cancel_and_wait(task)


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

    async def background_connect_mcp_servers() -> MCPClient | None:
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

    # Awaited below — opt out of supervisor logging to avoid duplicate logs.
    task = supervised_task(
        background_connect_mcp_servers(),
        name="mcp.connect",
        registry=background_tasks,
        on_exception=lambda _exc: None,
    )

    yield

    await cancel_and_wait(task)
    if task.cancelled():
        return

    mcp_client = task.result()
    if not mcp_client:
        return

    try:
        LOGGER.info("Disconnecting from all MCP servers")
        await mcp_client.disconnect_from_all_servers()
        LOGGER.info("Successfully disconnected from all MCP servers")
    except Exception as e:
        LOGGER.error(f"Error during MCP disconnect: {e}")


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
    workspace = manager.workspace
    mcp_server_enabled = state.mcp_server_enabled
    skew_protection_enabled = state.skew_protection

    # Startup message
    if not quiet:
        file = workspace.single_file()
        print_startup(
            file_name=file.name if file else None,
            url=_startup_url(state),
            run=manager.mode == SessionMode.RUN,
            new=workspace.get_unique_file_key() == NEW_FILE,
            network=state.host == "0.0.0.0",
            startup_tip=state.startup_tip,
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
async def server_registry(app: Starlette) -> AsyncIterator[None]:
    """Register this server in the local registry for discovery.

    Only servers started **without** an auth token (`--no-token`)
    are registered.  This ensures only servers that have explicitly
    opted into relaxed local access are discoverable.
    """
    from marimo._server.server_registry import (
        ServerRegistryEntry,
        ServerRegistryWriter,
    )

    state = AppState.from_app(app)

    # Guard: only register when the user has opted into relaxed local
    # access (no auth token).  Skew protection is irrelevant here —
    # it guards against frontend/server version mismatch and should
    # not prevent agent-oriented discovery.
    if state.enable_auth:
        LOGGER.debug(
            "Skipping server registry: auth=%s",
            state.enable_auth,
        )
        yield
        return

    entry = ServerRegistryEntry.from_server(
        host=state.host,
        port=state.port,
        base_url=state.base_url,
    )
    writer = ServerRegistryWriter(entry)
    try:
        writer.register()
    except Exception as e:
        LOGGER.warning("Failed to register server: %s", e)

    yield

    writer.deregister()


@contextlib.asynccontextmanager
async def etc(app: Starlette) -> AsyncIterator[None]:
    del app
    # Mimetypes
    initialize_mimetypes()
    yield


@contextlib.asynccontextmanager
async def reap_subprocesses(app: Starlette) -> AsyncIterator[None]:
    del app
    yield
    await cancel_pending_reaps()


def _startup_url(state: AppStateBase) -> str:
    url_host = format_url_host(state.host, state.port)
    port = state.port

    url = f"http://{url_host}:{port}{state.base_url}"
    if port == 80:
        url = f"http://{url_host}{state.base_url}"
    elif port == 443:
        url = f"https://{url_host}{state.base_url}"

    if AuthToken.is_empty(state.session_manager.auth_token):
        return url
    return f"{url}?access_token={state.session_manager.auth_token!s}"


def _mcp_startup_url(state: AppStateBase) -> str:
    url_host = format_url_host(state.host, state.port)
    port = state.port
    base_url = state.base_url

    # Construct MCP endpoint URL
    mcp_prefix = "/mcp"
    mcp_name = "server"
    full_mcp_path = f"{mcp_prefix}/{mcp_name}"
    url = f"http://{url_host}:{port}{base_url}{full_mcp_path}"
    if port == 80:
        url = f"http://{url_host}{base_url}{full_mcp_path}"
    elif port == 443:
        url = f"https://{url_host}{base_url}{full_mcp_path}"

    # Add access token if not empty
    if AuthToken.is_empty(state.session_manager.auth_token):
        return url
    return f"{url}?access_token={state.session_manager.auth_token!s}"
